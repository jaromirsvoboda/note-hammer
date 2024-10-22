#Requires -RunAsAdministrator

# Script to set up Android platform-tools and development environment
param(
    [string]$InstallPath = "C:\Android",
    [switch]$ForceInstall = $false,
    [switch]$SkipPythonSetup = $false
)

function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

function Test-Command($Command) {
    try {
        Get-Command $Command -ErrorAction Stop
        return $true
    }
    catch {
        return $false
    }
}

function Install-AndroidPlatformTools {
    param (
        [string]$InstallPath
    )
    
    Write-ColorOutput Green "Installing Android Platform Tools..."
    
    # Create installation directory
    if (-not (Test-Path $InstallPath)) {
        New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
    }
    
    $platformToolsPath = Join-Path $InstallPath "platform-tools"
    $zipPath = Join-Path $InstallPath "platform-tools.zip"
    
    # Download platform-tools
    Write-ColorOutput Yellow "Downloading platform-tools..."
    $url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
    
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $url -OutFile $zipPath
    }
    catch {
        Write-ColorOutput Red "Failed to download platform-tools: $_"
        exit 1
    }
    
    # Extract the zip
    Write-ColorOutput Yellow "Extracting files..."
    try {
        if (Test-Path $platformToolsPath) {
            Remove-Item $platformToolsPath -Recurse -Force
        }
        Expand-Archive -Path $zipPath -DestinationPath $InstallPath -Force
    }
    catch {
        Write-ColorOutput Red "Failed to extract platform-tools: $_"
        exit 1
    }
    
    # Clean up
    Remove-Item $zipPath -Force
    
    return $platformToolsPath
}

function Add-ToPath {
    param (
        [string]$PathToAdd
    )
    
    Write-ColorOutput Yellow "Adding to PATH..."
    
    # Get current Path values
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    
    # Check if path already exists
    if ($userPath -like "*$PathToAdd*") {
        Write-ColorOutput Yellow "Path already exists in USER PATH"
        return
    }
    
    # Add to PATH
    try {
        $newPath = "$userPath;$PathToAdd"
        [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
        $env:Path = "$env:Path;$PathToAdd"
        Write-ColorOutput Green "Successfully added to PATH"
    }
    catch {
        Write-ColorOutput Red "Failed to add to PATH: $_"
        exit 1
    }
}

function Initialize-PythonEnvironment {
    Write-ColorOutput Yellow "Setting up Python environment..."
    
    # Check if virtual environment exists
    if (-not (Test-Path ".\.venv")) {
        Write-ColorOutput Yellow "Creating virtual environment..."
        python -m venv .venv
    }
    
    # Activate virtual environment
    Write-ColorOutput Yellow "Activating virtual environment..."
    & .\.venv\Scripts\Activate.ps1
    
    # Install requirements
    Write-ColorOutput Yellow "Installing Python packages..."
    pip install -r requirements.txt
    
    # Initialize uiautomator2
    Write-ColorOutput Yellow "Initializing uiautomator2..."
    python -m uiautomator2 init
}

function Test-AndroidDevice {
    Write-ColorOutput Yellow "Testing ADB connection..."
    
    $devices = & adb devices
    if ($devices -match "device$") {
        Write-ColorOutput Green "Android device found and connected!"
        return $true
    }
    else {
        Write-ColorOutput Yellow @"
No Android device detected. Please:
1. Enable USB debugging on your Android device:
   - Go to Settings > About phone
   - Tap Build number 7 times to enable Developer options
   - Go back to Settings > System > Developer options
   - Enable USB debugging
2. Connect your device via USB
3. Accept the USB debugging prompt on your device
4. Run 'adb devices' to verify connection
"@
        return $false
    }
}

# Main script execution
Write-ColorOutput Cyan @"
===================================
Android Development Environment Setup
===================================
"@

# Check if ADB is already installed
if ((Test-Command "adb") -and -not $ForceInstall) {
    Write-ColorOutput Green "ADB is already installed and in PATH"
    $platformToolsPath = (Get-Command adb).Source | Split-Path -Parent
}
else {
    $platformToolsPath = Install-AndroidPlatformTools -InstallPath $InstallPath
    Add-ToPath -PathToAdd $platformToolsPath
}

# Set up Python environment if not skipped
if (-not $SkipPythonSetup) {
    Initialize-PythonEnvironment
}

# Test Android device connection
Test-AndroidDevice

Write-ColorOutput Cyan @"

Setup Complete!
==============
Platform Tools Location: $platformToolsPath
To verify installation, open a new PowerShell window and run:
- adb version
- python -m uiautomator2 --help

If you need to reconnect your device:
1. Enable USB debugging on your Android device
2. Connect via USB
3. Run 'adb devices' to verify connection
"@