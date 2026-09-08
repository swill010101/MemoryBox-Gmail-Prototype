[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ExpectedReleaseSha,
    [Parameter(Mandatory=$true)][string]$ApprovalReference,
    [Parameter(Mandatory=$true)][string]$ToolRelease,
    [switch]$Execute
)
$ErrorActionPreference='Stop'
$release=(Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$toolRoot=(Resolve-Path -LiteralPath $ToolRelease).Path
$python=Join-Path $toolRoot '.titanet-venv\Scripts\python.exe'
$preflight=Join-Path $PSScriptRoot 'prepare-eugene-t1-retirement.py'
$annotation='d5a3d050-76d6-446e-91d4-ff89986856cb'
$admission='1039c733-2149-40b2-b027-97058e032af3'
$patioAdmission='f59050d5-cb4b-4ff7-beee-609b28f7af61'
$backupRoot='C:\MemoryBox-backups'
$container='memorybox-pg'
function Require-LastExit([string]$message) { if($LASTEXITCODE -ne 0){throw $message} }
function DbJson([string]$query) {
  $out=docker exec $container psql -X -q -A -t -U memorybox -d memorybox -v ON_ERROR_STOP=1 -c $query
  Require-LastExit 'Database read failed.'
  return (($out|Where-Object{$_ -and $_.Trim()}) -join '')|ConvertFrom-Json
}
function Snapshot {
  DbJson "SELECT json_build_object('retirements',(SELECT count(*) FROM i13_voice_pilot_retirements),'recognition_queue',(SELECT count(*) FROM recognition_queue_items),'speech_queue',(SELECT count(*) FROM speech_queue_items),'words',(SELECT count(*) FROM speech_transcript_words),'annotations',(SELECT count(*) FROM i13_transcript_annotations),'eugene_stale',(SELECT stale FROM i13_voice_pilot_results WHERE admission_id='$admission'::uuid),'tom_stale',(SELECT stale FROM i13_voice_pilot_results WHERE admission_id='9e0a2605-8bfc-4ec7-aa6e-501f9bca7cea'::uuid),'n1_stale',(SELECT stale FROM i13_voice_pilot_results WHERE admission_id='46cb1d21-b464-4bc4-bf7c-7d0de0202ca6'::uuid),'patio_stale',(SELECT stale FROM i13_voice_pilot_results WHERE admission_id='$patioAdmission'::uuid));"
}
Push-Location $release
try {
  if((git rev-parse HEAD).Trim().ToLowerInvariant() -ne $ExpectedReleaseSha.ToLowerInvariant()){throw 'Release SHA mismatch.'}
  if(git status --porcelain){throw 'Release is not clean; preserve it and stop.'}
  if(-not $ApprovalReference.Trim()){throw 'Approval reference is required.'}
  if(-not $env:MEMORYBOX_DATABASE_URL){throw 'MEMORYBOX_DATABASE_URL is absent; use the configured FlightSim shell.'}
  if(-not (Test-Path -LiteralPath $python)){throw 'The verified TitaNet Python environment is unavailable.'}
  $check=& $python -B $preflight
  Require-LastExit 'T1 retirement preflight failed.'
  $checkJson=(($check|Where-Object{$_ -and $_.Trim()})-join "`n")|ConvertFrom-Json
  if($checkJson.annotation_id -ne $annotation -or $checkJson.admission_id -ne $admission){throw 'T1 retirement preflight identity mismatch.'}
  if(-not $Execute){[pscustomobject]@{ok=$true;mode='check_only';release_sha=$ExpectedReleaseSha.ToLowerInvariant();annotation_id=$annotation;admission_id=$admission;database_writes=$false;private_audio_processed=$false;reprocessing_started=$false}|ConvertTo-Json;exit 0}
  docker inspect $container|Out-Null;Require-LastExit 'memorybox-pg container is unavailable.'
  $before=Snapshot
  if($before.eugene_stale -or $before.tom_stale -or $before.n1_stale -or $before.patio_stale){throw 'Unexpected existing stale result; preserve and stop.'}
  $token=[guid]::NewGuid().ToString('N');$backupDir=Join-Path $backupRoot "i13-final-pre-t1-retirement-$token";$remoteDir="/tmp/mb-i13-final-pre-t1-retirement-$token"
  New-Item -ItemType Directory -Path $backupDir -ErrorAction Stop|Out-Null
  docker exec $container mkdir $remoteDir;Require-LastExit 'Container backup directory creation failed.'
  docker exec -e 'PGOPTIONS=-c default_transaction_read_only=on' $container pg_dump -U memorybox -d memorybox --format=custom --lock-wait-timeout=5000 --file="$remoteDir/memorybox.dump";Require-LastExit 'Fresh backup failed.'
  docker exec $container pg_restore --list "$remoteDir/memorybox.dump"|Out-Null;Require-LastExit 'Fresh backup archive inspection failed.'
  $containerHash=((docker exec $container sha256sum "$remoteDir/memorybox.dump") -split '\s+')[0];Require-LastExit 'Container backup hash failed.'
  $backupFile=Join-Path $backupDir 'memorybox.dump';docker cp "${container}:$remoteDir/memorybox.dump" $backupFile;Require-LastExit 'Backup copy failed.'
  $backupHash=(Get-FileHash -LiteralPath $backupFile -Algorithm SHA256).Hash.ToLowerInvariant();if($backupHash -ne $containerHash){throw 'Fresh backup hash mismatch.'}
  [pscustomobject]@{backup_file=$backupFile;bytes=(Get-Item -LiteralPath $backupFile).Length;sha256=$backupHash;container_hash_matches=$true}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $backupDir 'backup-proof.json') -Encoding UTF8
  $retired=& $python -B -m memorybox.processing.voice_pilot_cli retire --annotation-id $annotation --reason "T1 lifecycle proof; approval $ApprovalReference"
  Require-LastExit 'T1 retirement failed.'
  $retiredJson=(($retired|Where-Object{$_ -and $_.Trim()})-join "`n")|ConvertFrom-Json
  if($retiredJson.retired -ne $annotation -or @($retiredJson.affected_admissions).Count -ne 1 -or $retiredJson.affected_admissions[0] -ne $admission -or $retiredJson.reprocessing_started){throw 'T1 retirement result verification failed.'}
  $after=Snapshot
  foreach($field in 'recognition_queue','speech_queue','words','annotations'){if($before.$field -ne $after.$field){throw "Unexpected legacy count change: $field"}}
  if($after.retirements -ne ($before.retirements+1) -or -not $after.eugene_stale -or $after.tom_stale -or $after.n1_stale -or $after.patio_stale){throw 'T1 lifecycle outcome verification failed.'}
  [pscustomobject]@{ok=$true;release_sha=$ExpectedReleaseSha.ToLowerInvariant();annotation_id=$annotation;stale_admission=$admission;backup_file=$backupFile;backup_sha256=$backupHash;legacy_counts_unchanged=$true;tom_result_current=$true;n1_result_current=$true;patio_result_current=$true;private_audio_processed=$false;reprocessing_started=$false;automatic_retry=$false}|ConvertTo-Json
} finally {Pop-Location}
