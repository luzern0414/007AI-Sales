[CmdletBinding()]
param([switch]$ReuseCpuDependencies)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$cpuPython = Join-Path $projectRoot '.venv-asr\Scripts\python.exe'
$gpuEnvironment = Join-Path $projectRoot '.venv-asr-gpu'
$python = Join-Path $gpuEnvironment 'Scripts\python.exe'
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw '需要先安装 uv' }
if (-not (Test-Path -LiteralPath $cpuPython)) { throw '需要已验证的 .venv-asr CPU 环境' }
if (-not (Test-Path -LiteralPath $python)) {
    & uv venv $gpuEnvironment --python $cpuPython
    if ($LASTEXITCODE -ne 0) { throw '创建GPU环境失败' }
}
& uv pip install --python $python 'torch==2.5.1' 'torchaudio==2.5.1' --index-url 'https://download.pytorch.org/whl/cu121'
if ($LASTEXITCODE -ne 0) { throw '安装CUDA版PyTorch失败' }
$requirements = Join-Path $projectRoot 'output\funasr\gpu-requirements.txt'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $requirements) | Out-Null
Get-Content -LiteralPath (Join-Path $projectRoot 'config\funasr-batch.lock.txt') |
    Where-Object { $_ -notmatch '^(torch|torchaudio)==' } |
    Set-Content -LiteralPath $requirements -Encoding utf8
if ($ReuseCpuDependencies) {
    # Same Python interpreter and pinned common packages; own copies, no .pth link.
    $copyScript = @'
from pathlib import Path
import shutil
import sys
root=Path(sys.argv[1]).resolve()
source=root/'.venv-asr/Lib/site-packages'
target=root/'.venv-asr-gpu/Lib/site-packages'
assert target.resolve().is_relative_to(root) and target.parents[1].name=='.venv-asr-gpu'
for item in target.glob('*.dist-info'):
    if not item.name.startswith(('torch-','torchaudio-')) and not (source/item.name).exists():
        shutil.rmtree(item)
for item in source.iterdir():
    name=item.name.lower()
    if name in ('torch','torchaudio','torchgen','functorch','__pycache__') or name.startswith(('torch-','torchaudio-')):
        continue
    destination=target/item.name
    if item.is_dir():
        shutil.copytree(item,destination,dirs_exist_ok=True)
    else:
        shutil.copy2(item,destination)
'@
    & $cpuPython -c $copyScript $projectRoot
    if ($LASTEXITCODE -ne 0) { throw '复制已验证的通用依赖失败' }
} else {
    & uv pip install --python $python --no-deps -r $requirements
    if ($LASTEXITCODE -ne 0) { throw '安装FunASR依赖失败' }
}
& uv pip check --python $python
if ($LASTEXITCODE -ne 0) { throw 'GPU环境依赖一致性验证失败' }
& $python -c 'import torch, torchaudio; print(torch.__version__, torchaudio.__version__, torch.version.cuda); assert torch.cuda.is_available(), "CUDA unavailable"; print(torch.cuda.get_device_name(0)); print((torch.ones(4,device="cuda:0")*2).cpu())'
if ($LASTEXITCODE -ne 0) { throw 'CUDA实算验证失败；CPU环境未改动' }
