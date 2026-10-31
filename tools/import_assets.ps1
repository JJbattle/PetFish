param(
    [Parameter(Mandatory = $true)][string]$GodotExe,
    [Parameter(Mandatory = $true)][string]$GamePath
)

$ErrorActionPreference = 'Stop'
$gameRoot = (Resolve-Path -LiteralPath $GamePath).Path
$godotPath = (Resolve-Path -LiteralPath $GodotExe).Path
$logRoot = Join-Path $gameRoot '.godot'
[void](New-Item -ItemType Directory -Path $logRoot -Force)
$stdout = Join-Path $logRoot 'fishpet-import.log'
$stderr = Join-Path $logRoot 'fishpet-import-errors.log'
$arguments = @('--headless', '--path', ('"' + $gameRoot + '"'), '--editor', '--import', '--quit')
$child = $null
$previousAppData = $env:APPDATA
try {
    # Import only: never instantiate the transparent/topmost main scene.
    # Headless importing must not save over the user's Godot editor settings.
    $env:APPDATA = Join-Path $logRoot 'import-profile'
    [void](New-Item -ItemType Directory -Path $env:APPDATA -Force)
    $child = Start-Process -FilePath $godotPath -ArgumentList $arguments `
        -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $ownedHandle = $child.Handle
    if (-not $child.WaitForExit(45000)) {
        Stop-Process -Id $child.Id -Force -ErrorAction SilentlyContinue
        throw 'Godot resource import timed out; its owned process was stopped.'
    }
    $child.WaitForExit()
    if ($child.ExitCode -ne 0) {
        throw "Godot resource import failed ($($child.ExitCode)); see $stderr"
    }
    $errors = Get-Content -LiteralPath $stderr -Raw -ErrorAction SilentlyContinue
    if ($errors -match 'SCRIPT ERROR:|Parse Error:|Failed to import') {
        throw "Godot reported an import/script error; see $stderr"
    }
    Write-Output 'FishPet assets imported successfully.'
    exit 0
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
} finally {
    $env:APPDATA = $previousAppData
    if ($null -ne $child) { $child.Dispose() }
}
