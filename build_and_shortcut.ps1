# build_and_shortcut.ps1
# Run from project folder (where donna_app.py and donna.jpg live)
# Usage: Open PowerShell, activate venv, then: .\build_and_shortcut.ps1

param(
    [string]$IconSrc = "your_icon.png",   # change to your file if needed (png/jpg/ico)
    [string]$Portrait = "donna.jpg",
    [string]$AppPy = "donna_app.py",
    [string]$ExeName = "donna_app.exe"
)

Set-StrictMode -Version Latest
$here = Split-Path -Parent $MyInvocation.MyCommand.Definition
Push-Location $here

# Ensure files exist
if (!(Test-Path $AppPy)) { Write-Error "$AppPy not found in $here"; exit 1 }
if (!(Test-Path $Portrait)) { Write-Error "$Portrait not found in $here"; exit 1 }
if (!(Test-Path $IconSrc)) { Write-Error "$IconSrc not found in $here"; exit 1 }

# if icon is not .ico convert it to donna_icon.ico using Python script (requires pillow installed)
$icoName = "donna_icon.ico"
if ($IconSrc.ToLower().EndsWith(".ico")) {
    Copy-Item $IconSrc -Destination $icoName -Force
    Write-Host "Using existing ICO: $IconSrc -> $icoName"
} else {
    $py = @"
from PIL import Image
img = Image.open(r'$IconSrc').convert('RGBA')
w,h = img.size
s = max(w,h)
new = Image.new('RGBA',(s,s),(0,0,0,0))
new.paste(img, ((s-w)//2, (s-h)//2), img)
new = new.resize((512,512), Image.LANCZOS)
icon_sizes = [(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)]
new.save(r'$icoName', format='ICO', sizes=icon_sizes)
print('Wrote', r'$icoName')
"@
    $tmpPy = Join-Path $env:TEMP "make_icon_temp.py"
    $py | Out-File -FilePath $tmpPy -Encoding utf8
    python $tmpPy
    Remove-Item $tmpPy -Force
    Write-Host "Converted $IconSrc -> $icoName"
}

# Build exe with pyinstaller (bundle the portrait image)
# Use --onefile; if you get issues, remove --onefile to test --onedir
$addData = "$Portrait;."
Write-Host "Running PyInstaller..."
pyinstaller --noconfirm --windowed --onefile --icon=$icoName --add-data $addData $AppPy

# Locate produced exe
$distExe = Join-Path $here "dist\$ExeName"
if (!(Test-Path $distExe)) {
    # If the exe has a different name (pyinstaller may name it py file without underscores), try to find exe
    $possible = Get-ChildItem -Path (Join-Path $here "dist") -Filter *.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($possible) {
        $distExe = $possible.FullName
    } else {
        Write-Error "Build finished but EXE not found in dist. Check PyInstaller output."
        Pop-Location
        exit 1
    }
}

Write-Host "Built EXE at: $distExe"

# Create Desktop shortcut with icon
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Donna.lnk"
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $distExe
$shortcut.WorkingDirectory = Split-Path $distExe
$shortcut.WindowStyle = 1
$shortcut.IconLocation = Join-Path $here $icoName
$shortcut.Save()
Write-Host "Desktop shortcut created at $shortcutPath"

Pop-Location
