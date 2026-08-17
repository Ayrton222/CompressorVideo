$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvDir = Join-Path $projectDir ".venv"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    $pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -eq $pythonLauncher) {
        $pythonLauncher = Get-Command python -ErrorAction SilentlyContinue
    }

    if ($null -eq $pythonLauncher) {
        throw "Python nao encontrado. Instale Python 3.10 ou superior e tente novamente."
    }

    Write-Host "Criando o ambiente virtual em .venv..."
    if ($pythonLauncher.Name -eq "py.exe") {
        & $pythonLauncher.Source -3 -m venv $venvDir
    } else {
        & $pythonLauncher.Source -m venv $venvDir
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Nao foi possivel criar o ambiente virtual em .venv."
}

& $pythonExe -m pip install -r (Join-Path $projectDir "requirements-build.txt")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $pythonExe -m PyInstaller --noconfirm --clean (Join-Path $projectDir "CompressorVideo.spec")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Executavel criado em: $(Join-Path $projectDir 'dist\CompressorVideo.exe')"
