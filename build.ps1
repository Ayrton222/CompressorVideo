$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectDir ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Ambiente virtual não encontrado em .venv. Configure o interpretador do projeto no PyCharm primeiro."
}

& $pythonExe -m pip install -r (Join-Path $projectDir "requirements-build.txt")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $pythonExe -m PyInstaller --noconfirm --clean (Join-Path $projectDir "CompressorVideo.spec")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Executável criado em: $(Join-Path $projectDir 'dist\CompressorVideo.exe')"
