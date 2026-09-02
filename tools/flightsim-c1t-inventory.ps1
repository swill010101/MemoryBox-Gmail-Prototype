param(
    [string]$OutDir = "C:\memorybox\docs\test-output\c1t-benchmark\inventory",
    [string]$OllamaBaseUrl = "http://127.0.0.1:11434",
    [string]$Model = "gemma4:26b",
    [switch]$IncludeMsinfo32
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$arguments = @(
    "-m", "memorybox", "c1t-inventory",
    "--out-dir", $OutDir,
    "--ollama-base-url", $OllamaBaseUrl,
    "--model", $Model
)
if ($IncludeMsinfo32) {
    $arguments += "--include-msinfo32"
}

& python @arguments
exit $LASTEXITCODE
