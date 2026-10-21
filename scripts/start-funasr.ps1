[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)][int]$Port = 10096,
    [ValidateRange(1, 16)][int]$Threads = 4,
    [ValidateSet('cpu', 'cuda:0', 'auto')][string]$Device = 'cpu'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$environment = if ($Device -eq 'cpu') { '.venv-asr' } else { '.venv-asr-gpu' }
$python = Join-Path $projectRoot "$environment\Scripts\python.exe"
if ($Device -eq 'auto' -and -not (Test-Path -LiteralPath $python)) {
    $python = Join-Path $projectRoot '.venv-asr\Scripts\python.exe'
}
$models = Join-Path $projectRoot 'output\funasr\models'
if (-not (Test-Path -LiteralPath $python)) { throw '缺少本地转写环境' }
foreach ($alias in 'paraformer-zh', 'paraformer-zh-streaming', 'fsmn-vad', 'ct-punc') {
    if (-not (Test-Path -LiteralPath (Join-Path $models "$alias\model.pt"))) {
        throw "缺少模型：$alias"
    }
}
$env:PYTHONUTF8 = '1'
Push-Location -LiteralPath $projectRoot
try {
    & $python -u -m scripts.funasr_service --model-dir $models --port $Port --threads $Threads --device $Device
    if ($LASTEXITCODE -ne 0) { throw "转写服务退出：$LASTEXITCODE" }
} finally {
    Pop-Location
}
