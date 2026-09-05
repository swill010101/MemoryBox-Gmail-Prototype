param([Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{40}$')][string]$ExpectedSha)
$ErrorActionPreference='Stop'
$i13Release=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../../..')).Path
$i13Head=git -C $i13Release rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $i13Head -ne $ExpectedSha) { throw 'Release commit mismatch.' }
$i13Status=git -C $i13Release status --porcelain
if ($LASTEXITCODE -ne 0 -or $i13Status) { throw 'Release must be clean.' }
$i13TestDb='mb_i13_pre031_restore_d963b73540f14ce7a07eea86df20b156'
$i13Migration=Get-Content -Raw -LiteralPath (Join-Path $i13Release 'memorybox/migrations/031_p2_i13_transcript_annotations.sql')
$i13Old=git -C $i13Release show '195725ddc49b22d127c98f037ec26104196df4eb:memorybox/migrations/031_p2_i13_transcript_annotations.sql'
if ($LASTEXITCODE -ne 0) { throw 'Baseline migration unavailable.' }
$i13Old=$i13Old -join "`n"
$i13Offset=$i13Old.IndexOf('CREATE VIEW i13_effective_words AS')
if ($i13Offset -lt 0) { throw 'Baseline view missing.' }
$i13OldViews=$i13Old.Substring($i13Offset).Replace('i13_effective_words','i13_before_words').Replace('i13_effective_moments','i13_before_moments')
$i13Before=@'
\timing on
BEGIN;
SET LOCAL search_path=public;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='120s';
DO $$ BEGIN
 IF current_database()<>'mb_i13_pre031_restore_d963b73540f14ce7a07eea86df20b156' THEN RAISE EXCEPTION 'Wrong database'; END IF;
 IF to_regclass('public.i13_transcript_versions') IS NOT NULL THEN RAISE EXCEPTION 'Rehearsal schema already present'; END IF;
END $$;
'@
$i13After=@'
SET LOCAL statement_timeout='20s';
SELECT count(*) AS archived_words,count(*) FILTER(WHERE o.id IS NULL OR to_jsonb(o)<>w.word) AS snapshot_mismatches
FROM i13_transcript_versions v CROSS JOIN LATERAL jsonb_array_elements(v.machine->'words') w(word)
LEFT JOIN speech_transcript_words o ON o.id=(w.word->>'id')::uuid;
'@
foreach ($i13Kind in @('words','moments')) {
 $i13SourceColumn=if ($i13Kind -eq 'words') {'source_id'} else {'video_external_id'}
 $i13ProviderColumn=if ($i13Kind -eq 'words') {'provider_key'} else {'video_provider_key'}
 $i13Predicate="$i13ProviderColumn='hvrt' AND $i13SourceColumn IN ('vid-da41273dbd9ac4bb','vid-c57dbd21f993f6d1')"
 $i13BeforeQuery="SELECT * FROM i13_before_$i13Kind WHERE $i13Predicate"
 $i13AfterQuery="SELECT * FROM i13_effective_$i13Kind WHERE $i13Predicate"
 $i13After+="`nSELECT NOT EXISTS(($i13BeforeQuery EXCEPT ALL $i13AfterQuery) UNION ALL ($i13AfterQuery EXCEPT ALL $i13BeforeQuery)) AS $($i13Kind)_results_identical;`n"
}
$i13After+=@'
EXPLAIN (ANALYZE,BUFFERS,TIMING OFF)
SELECT * FROM i13_effective_words WHERE provider_key='hvrt' AND source_id='vid-da41273dbd9ac4bb' ORDER BY word_index;
EXPLAIN (ANALYZE,BUFFERS,TIMING OFF)
SELECT * FROM i13_effective_moments WHERE video_provider_key='hvrt' AND video_external_id='vid-da41273dbd9ac4bb' ORDER BY t_start;
ROLLBACK;
SELECT current_database() AS rehearsal_database,to_regclass('public.i13_transcript_versions') IS NULL AS rehearsal_rolled_back;
'@
($i13Before+"`n"+$i13Migration+"`n"+$i13OldViews+"`n"+$i13After) |
 docker exec -i memorybox-pg psql -X -U memorybox -d $i13TestDb -v ON_ERROR_STOP=1
if ($LASTEXITCODE -ne 0) { throw 'Rehearsal failed; disconnected transaction rolls back. Preserve output and do not raise timeouts.' }
