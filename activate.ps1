#Requires -Version 5.1
# ======================================================================
# Grupo: Fabio Durán · Gustavo Reyes · Ezequiel Muñoz
# Archivo: activate.ps1
# Objetivo: Desactiva conda y activa el entorno virtual del proyecto en PowerShell; crea .venv si falta y, con -Sync, ejecuta uv sync.
# Creado: 20261026_2207 (America/Santiago)
# Actualizado: 20261101_1735 (America/Santiago)
# ======================================================================

<#
.SYNOPSIS
    Prepara la sesión de PowerShell para este proyecto.

.DESCRIPTION
    Desactiva cualquier entorno conda activo (por ejemplo el "base" que
    Anaconda/Miniconda deja por defecto), activa el .venv del proyecto y
    muestra el proveedor de LLM configurado en .env. Si no existe .venv lo
    crea con Python 3.12 e instala requirements.txt.

.PARAMETER Sync
    Además de activar, ejecuta "uv sync" (requiere uv instalado).

.EXAMPLE
    .\activate.ps1

.EXAMPLE
    .\activate.ps1 -Sync

.NOTES
    Para salir del entorno virtual:  deactivate

    Si la política de ejecución bloquea el script:
        powershell -ExecutionPolicy Bypass -File .\activate.ps1
#>
[CmdletBinding()]
param(
    [switch] $Sync
)

$ErrorActionPreference = 'Stop'

$ProjectRoot    = $PSScriptRoot
$VenvDir        = Join-Path $ProjectRoot '.venv'
$VenvPython     = Join-Path $VenvDir 'Scripts\python.exe'
$ActivateScript = Join-Path $VenvDir 'Scripts\Activate.ps1'
$Requirements   = Join-Path $ProjectRoot 'requirements.txt'

function Write-Step { param([string] $Message) Write-Host "==> $Message" -ForegroundColor Cyan }
function Write-Ok   { param([string] $Message) Write-Host "    OK  $Message" -ForegroundColor Green }
function Write-Warn { param([string] $Message) Write-Host "    !   $Message" -ForegroundColor Yellow }

function Remove-CondaFromPath {
    <#
        Quita del PATH las entradas de la instalación de conda indicada.
        Devuelve cuántas entradas se quitaron.
    #>
    param([Parameter(Mandatory)][string] $CondaPrefix)

    $normalized = $CondaPrefix.TrimEnd('\', '/')
    $entries    = @($env:PATH -split ';' | Where-Object { $_ -ne '' })
    $kept       = @(
        foreach ($entry in $entries) {
            $trimmed = $entry.TrimEnd('\', '/')
            $isConda = ($trimmed -ieq $normalized) -or
                       $trimmed.StartsWith($normalized + '\', [System.StringComparison]::OrdinalIgnoreCase) -or
                       $trimmed.StartsWith($normalized + '/', [System.StringComparison]::OrdinalIgnoreCase)
            if (-not $isConda) { $entry }
        }
    )

    $env:PATH = $kept -join ';'
    return ($entries.Count - $kept.Count)
}

function Remove-VenvFromPath {
    param([Parameter(Mandatory)][string] $VenvPath)

    $normalized = $VenvPath.TrimEnd('\', '/')
    $entries    = @($env:PATH -split ';' | Where-Object { $_ -ne '' })
    $kept       = @(
        foreach ($entry in $entries) {
            $trimmed = $entry.TrimEnd('\', '/')
            if ($trimmed -ine $normalized -and
                -not $trimmed.StartsWith($normalized + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
                $entry
            }
        }
    )

    $env:PATH = $kept -join ';'
}

# ---------------------------------------------------------------------------
# 1. Desactivar conda (base por defecto)
# ---------------------------------------------------------------------------
$condaPrefix = $env:CONDA_PREFIX
$condaActive = [bool]($condaPrefix -or $env:CONDA_DEFAULT_ENV)
$condaName   = if ($env:CONDA_DEFAULT_ENV) { $env:CONDA_DEFAULT_ENV }
               elseif ($condaPrefix) { Split-Path $condaPrefix -Leaf }
               else { 'conda' }

if (-not $condaActive) {
    Write-Step 'conda no está activo en esta sesión.'
}
else {
    Write-Step "Desactivando conda ($condaName)..."

    # 'conda deactivate' sólo funciona si conda init registró el hook de shell
    # (queda como función o como alias). Si 'conda' es únicamente el .bat/.exe,
    # el comando no hace nada: se detecta por falta de progreso y se usa el
    # respaldo manual.
    $levels = 0
    if (Get-Command conda -ErrorAction SilentlyContinue) {
        while (($env:CONDA_PREFIX -or $env:CONDA_DEFAULT_ENV) -and $levels -lt 10) {
            $prefixBefore = $env:CONDA_PREFIX
            $shlvlBefore  = $env:CONDA_SHLVL

            try { conda deactivate *> $null } catch { break }
            $levels++

            if ($env:CONDA_PREFIX -eq $prefixBefore -and $env:CONDA_SHLVL -eq $shlvlBefore) {
                $levels = 0
                break
            }
        }
    }

    if ($env:CONDA_PREFIX -or $env:CONDA_DEFAULT_ENV) {
        $removed = 0
        if ($env:CONDA_PREFIX) { $removed = Remove-CondaFromPath -CondaPrefix $env:CONDA_PREFIX }

        foreach ($name in 'CONDA_PREFIX', 'CONDA_DEFAULT_ENV', 'CONDA_PROMPT_MODIFIER', 'CONDA_SHLVL', 'CONDA_PYTHON_EXE') {
            Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
        }

        Write-Ok "conda desactivado (limpieza manual del PATH: $removed entrada(s))"
        Write-Warn "Si el prompt sigue mostrando ($condaName), abrí una consola nueva."
    }
    else {
        Write-Ok "conda desactivado ($levels nivel(es) de anidamiento)"
    }
}

# ---------------------------------------------------------------------------
# 2. Asegurar el entorno virtual (Python 3.12)
# ---------------------------------------------------------------------------
if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Step 'No existe .venv: creando con Python 3.12...'

    $interpreter = $null
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        try { $interpreter = (& uv python find 3.12 2>$null | Select-Object -First 1) } catch { $interpreter = $null }
    }
    if (-not $interpreter -and (Get-Command python -ErrorAction SilentlyContinue)) {
        $interpreter = (Get-Command python).Source
    }
    if (-not $interpreter) {
        throw 'No se encontró Python 3.12 ni uv para crearlo.'
    }

    & $interpreter -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear .venv (código $LASTEXITCODE)." }
    Write-Ok "entorno creado con $interpreter"

    Write-Step 'Instalando requirements.txt...'
    & $VenvPython -m pip install -r $Requirements --disable-pip-version-check
    if ($LASTEXITCODE -ne 0) { throw "pip install falló (código $LASTEXITCODE)." }
    Write-Ok 'dependencias instaladas'
}
else {
    Write-Ok '.venv encontrado.'
}

if ($Sync) {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw 'Se pidió -Sync pero uv no está instalado.'
    }
    Write-Step 'Sincronizando con uv...'
    Push-Location $ProjectRoot
    try {
        & uv sync
        if ($LASTEXITCODE -ne 0) { throw "uv sync falló (código $LASTEXITCODE)." }
    }
    finally {
        Pop-Location
    }
    Write-Ok 'uv.lock al día.'
}

# ---------------------------------------------------------------------------
# 3. Activar el entorno virtual del proyecto
# ---------------------------------------------------------------------------
Write-Step 'Activando el entorno virtual del proyecto...'

if ($env:VIRTUAL_ENV -and ($env:VIRTUAL_ENV.TrimEnd('\') -ine $VenvDir)) {
    Remove-VenvFromPath -VenvPath $env:VIRTUAL_ENV
    Remove-Item -Path 'Env:VIRTUAL_ENV_PROMPT' -ErrorAction SilentlyContinue
    Write-Ok "entorno virtual anterior desactivado ($(Split-Path $env:VIRTUAL_ENV -Leaf))"
    Remove-Item -Path 'Env:VIRTUAL_ENV' -ErrorAction SilentlyContinue
}

if (Test-Path -LiteralPath $ActivateScript) {
    $processPolicy = Get-ExecutionPolicy -Scope Process
    if ($processPolicy -in @('Restricted', 'AllSigned')) {
        try { Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force }
        catch { Write-Warn "No se pudo ajustar la política de ejecución: $($_.Exception.Message)" }
    }

    . $ActivateScript
}
else {
    Write-Warn 'No se encontró Activate.ps1; configurando el entorno manualmente.'
    $env:VIRTUAL_ENV        = $VenvDir
    $env:VIRTUAL_ENV_PROMPT = 'taller-final-curso-1'
    $env:PATH               = (Join-Path $VenvDir 'Scripts') + ';' + $env:PATH
    Remove-Item -Path 'Env:PYTHONHOME' -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------------------
# 4. Verificación
# ---------------------------------------------------------------------------
Write-Step 'Verificando la sesión...'

$env:VIRTUAL_ENV        = $VenvDir
$env:VIRTUAL_ENV_PROMPT = 'taller-final-curso-1'

$pythonVersion = (& $VenvPython --version 2>&1 | Out-String).Trim()
Write-Ok "Python: $pythonVersion"

if ($env:CONDA_PREFIX) { Write-Warn "conda sigue activo en $($env:CONDA_PREFIX)" }
else { Write-Ok 'conda inactivo.' }

$activePython = (Get-Command python -ErrorAction SilentlyContinue).Source
if ($activePython -and -not $activePython.StartsWith($VenvDir, [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Warn "el comando 'python' aún resuelve a $activePython"
}
else {
    Write-Ok "python -> $activePython"
}

# Proveedor configurado (nunca se muestran claves)
$dotenv = Join-Path $ProjectRoot '.env'
if (Test-Path -LiteralPath $dotenv) {
    $valores = @{}
    Get-Content -LiteralPath $dotenv | ForEach-Object {
        if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') { $valores[$matches[1]] = $matches[2].Trim() }
    }
    $proveedor = if ($valores['LLM_PROVIDER']) { $valores['LLM_PROVIDER'] } else { 'google (default -> fallback ollama si falta clave)' }
    $modelo    = if ($valores['MODELO']) { $valores['MODELO'] } else { '(default del proveedor)' }
    $redisUrl  = if ($valores['REDIS_URL']) { $valores['REDIS_URL'] } elseif ($valores['REDIS_HOST']) { "redis://$($valores['REDIS_HOST']):$($valores['REDIS_PORT'])" } else { 'redis://localhost:6379' }
    $redisSafe = $redisUrl -replace '(redis(?:s)?://[^:/@\s]*:)([^@\s]+)(@)', '$1***$3'
    Write-Ok "LLM: $proveedor / $modelo"
    Write-Ok "Redis RAG: $redisSafe"
}
else {
    Write-Warn 'No hay .env; copiá .env.example a .env.'
}

Write-Host ''
Write-Host 'Entorno listo. Próximos pasos:' -ForegroundColor Cyan
Write-Host '  python main.py bodega "¿cuántos cascos hay?" --saltos'
Write-Host '  python -m src.bodega.evaluacion                        # correr Golden Set (20 casos)'
Write-Host '  jupyter nbconvert --to notebook --execute --inplace notebooks/agente_bodega.ipynb'
Write-Host '  deactivate                                             # salir del entorno virtual'
