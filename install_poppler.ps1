# ============================================================================
# POPPLER AUTOMATIC INSTALLER FOR WINDOWS
# ============================================================================
# This script will:
# 1. Download latest poppler for Windows
# 2. Extract to C:\poppler
# 3. Add to System PATH
# 4. Verify installation
# ============================================================================

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  POPPLER AUTOMATIC INSTALLER FOR WINDOWS" -ForegroundColor Yellow
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "⚠️  WARNING: Not running as Administrator!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "This script needs Administrator privileges to:" -ForegroundColor White
    Write-Host "  • Install to C:\poppler" -ForegroundColor Gray
    Write-Host "  • Modify System PATH" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Please:" -ForegroundColor White
    Write-Host "  1. Right-click PowerShell" -ForegroundColor Gray
    Write-Host "  2. Select 'Run as Administrator'" -ForegroundColor Gray
    Write-Host "  3. Run this script again" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Or run:" -ForegroundColor Cyan
    Write-Host "  Start-Process powershell -Verb runAs -ArgumentList '-File `"$PSCommandPath`"'" -ForegroundColor White
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "✓ Running as Administrator" -ForegroundColor Green
Write-Host ""

# ============================================================================
# STEP 1: Download Poppler
# ============================================================================

Write-Host "[1/5] Downloading Poppler..." -ForegroundColor Cyan

$popplerUrl = "https://github.com/oschwartz10612/poppler-windows/releases/download/v24.08.0-0/Release-24.08.0-0.zip"
$downloadPath = "$env:TEMP\poppler.zip"
$extractPath = "C:\poppler"

Write-Host "  → URL: $popplerUrl" -ForegroundColor Gray
Write-Host "  → Downloading to: $downloadPath" -ForegroundColor Gray

try {
    # Enable TLS 1.2 for GitHub
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    
    # Download with progress
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $popplerUrl -OutFile $downloadPath -UseBasicParsing
    $ProgressPreference = 'Continue'
    
    Write-Host "  ✓ Download complete!" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "  ✗ Download failed: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Manual download:" -ForegroundColor Yellow
    Write-Host "  1. Open: https://github.com/oschwartz10612/poppler-windows/releases" -ForegroundColor Gray
    Write-Host "  2. Download latest Release-XX.XX.X-0.zip" -ForegroundColor Gray
    Write-Host "  3. Extract to C:\poppler" -ForegroundColor Gray
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# ============================================================================
# STEP 2: Extract Poppler
# ============================================================================

Write-Host "[2/5] Extracting Poppler..." -ForegroundColor Cyan

# Remove old installation if exists
if (Test-Path $extractPath) {
    Write-Host "  → Removing old installation..." -ForegroundColor Gray
    Remove-Item -Path $extractPath -Recurse -Force
}

Write-Host "  → Extracting to: $extractPath" -ForegroundColor Gray

try {
    Expand-Archive -Path $downloadPath -DestinationPath $extractPath -Force
    
    # Check if extraction created nested folder
    $nestedFolder = Get-ChildItem -Path $extractPath -Directory | Select-Object -First 1
    if ($nestedFolder -and (Test-Path "$extractPath\$($nestedFolder.Name)\Library\bin")) {
        Write-Host "  → Moving files from nested folder..." -ForegroundColor Gray
        Get-ChildItem -Path "$extractPath\$($nestedFolder.Name)" | Move-Item -Destination $extractPath -Force
        Remove-Item -Path "$extractPath\$($nestedFolder.Name)" -Force
    }
    
    Write-Host "  ✓ Extraction complete!" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "  ✗ Extraction failed: $_" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# ============================================================================
# STEP 3: Verify Files
# ============================================================================

Write-Host "[3/5] Verifying installation..." -ForegroundColor Cyan

$binPath = "$extractPath\Library\bin"
$pdfinfoPath = "$binPath\pdfinfo.exe"

if (Test-Path $pdfinfoPath) {
    Write-Host "  ✓ Found: $pdfinfoPath" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "  ✗ pdfinfo.exe not found!" -ForegroundColor Red
    Write-Host "  Expected: $pdfinfoPath" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Files in $extractPath:" -ForegroundColor Yellow
    Get-ChildItem -Path $extractPath -Recurse -File | Select-Object -First 10 | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# ============================================================================
# STEP 4: Add to System PATH
# ============================================================================

Write-Host "[4/5] Adding to System PATH..." -ForegroundColor Cyan

try {
    # Get current PATH
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    
    # Check if already in PATH
    if ($currentPath -like "*$binPath*") {
        Write-Host "  → Already in PATH, updating..." -ForegroundColor Gray
        # Remove old entries
        $newPath = ($currentPath -split ';' | Where-Object { $_ -notlike "*poppler*" }) -join ';'
        $currentPath = $newPath
    }
    
    # Add to PATH
    $newPath = "$currentPath;$binPath"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "Machine")
    
    Write-Host "  ✓ Added to PATH: $binPath" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "  ✗ Failed to modify PATH: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Manual PATH setup:" -ForegroundColor Yellow
    Write-Host "  1. Press Win + R" -ForegroundColor Gray
    Write-Host "  2. Type: sysdm.cpl" -ForegroundColor Gray
    Write-Host "  3. Advanced → Environment Variables" -ForegroundColor Gray
    Write-Host "  4. Edit System 'Path'" -ForegroundColor Gray
    Write-Host "  5. Add: $binPath" -ForegroundColor Gray
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# ============================================================================
# STEP 5: Verify Installation
# ============================================================================

Write-Host "[5/5] Verifying installation..." -ForegroundColor Cyan

# Update PATH in current session
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine")

# Test pdfinfo
try {
    $pdfinfoVersion = & "$pdfinfoPath" -v 2>&1
    Write-Host "  ✓ pdfinfo works!" -ForegroundColor Green
    Write-Host "  Version: $($pdfinfoVersion[0])" -ForegroundColor Gray
    Write-Host ""
} catch {
    Write-Host "  ⚠️  pdfinfo test failed, but files are installed" -ForegroundColor Yellow
    Write-Host "  You may need to restart your terminal/IDE" -ForegroundColor Gray
    Write-Host ""
}

# Cleanup
Remove-Item -Path $downloadPath -Force -ErrorAction SilentlyContinue

# ============================================================================
# SUCCESS!
# ============================================================================

Write-Host "================================================================================" -ForegroundColor Green
Write-Host "  ✓ INSTALLATION COMPLETE!" -ForegroundColor Yellow
Write-Host "================================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Poppler installed to:" -ForegroundColor Cyan
Write-Host "  $extractPath" -ForegroundColor White
Write-Host ""
Write-Host "Added to System PATH:" -ForegroundColor Cyan
Write-Host "  $binPath" -ForegroundColor White
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Yellow
Write-Host "  1. Close and reopen your terminal/IDE/PowerShell" -ForegroundColor White
Write-Host "  2. Run: pdfinfo -v" -ForegroundColor Cyan
Write-Host "  3. If version shows, you're ready!" -ForegroundColor White
Write-Host "  4. Run your OCR app and try PDF files" -ForegroundColor White
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Green
Write-Host ""

Read-Host "Press Enter to exit"

