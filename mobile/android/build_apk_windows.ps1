$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Android SDK: Android Studio default location is enough for most employee/dev PCs.
$env:ANDROID_HOME = if ($env:ANDROID_HOME) {
    $env:ANDROID_HOME
} elseif (Test-Path "$env:LOCALAPPDATA\Android\Sdk") {
    "$env:LOCALAPPDATA\Android\Sdk"
} else {
    throw "Android SDK not found. Install Android Studio and Android SDK Platform 35 + Build-Tools 35.x."
}
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME

if (-not (Test-Path "keystore.properties")) {
    throw "Signing key is missing. Run .\generate_keystore_windows.cmd once. KEEP the generated JKS for every future APK update."
}

# Prefer Java already on PATH; otherwise use Android Studio's bundled JBR.
$java = Get-Command java.exe -ErrorAction SilentlyContinue
if (-not $java) {
    $studioJava = "C:\Program Files\Android\Android Studio\jbr\bin\java.exe"
    if (Test-Path $studioJava) {
        $env:JAVA_HOME = Split-Path (Split-Path $studioJava -Parent) -Parent
        $env:Path = "$env:JAVA_HOME\bin;$env:Path"
    } else {
        throw "Java not found. Android Studio's bundled JBR or JDK 17+ is required."
    }
}

# Use system Gradle when available. Otherwise download a private Gradle distribution
# into this source tree. Nothing is installed system-wide.
$gradle = Get-Command gradle.bat -ErrorAction SilentlyContinue
if (-not $gradle) { $gradle = Get-Command gradle -ErrorAction SilentlyContinue }
if ($gradle) {
    $gradleExe = $gradle.Source
} else {
    $gradleVersion = "8.9"
    $tools = Join-Path $PSScriptRoot ".tools"
    $gradleHome = Join-Path $tools "gradle-$gradleVersion"
    $gradleExe = Join-Path $gradleHome "bin\gradle.bat"
    if (-not (Test-Path $gradleExe)) {
        New-Item -ItemType Directory -Force -Path $tools | Out-Null
        $zip = Join-Path $tools "gradle-$gradleVersion-bin.zip"
        Write-Host "Gradle not found. Downloading Gradle $gradleVersion..." -ForegroundColor Yellow
        Invoke-WebRequest -UseBasicParsing "https://services.gradle.org/distributions/gradle-$gradleVersion-bin.zip" -OutFile $zip
        Expand-Archive -Path $zip -DestinationPath $tools -Force
        Remove-Item $zip -Force
    }
}

Write-Host "Building signed R-Messanger Android 15.1.2 (APK + AAB)..." -ForegroundColor Cyan
& $gradleExe --no-daemon clean assembleRelease bundleRelease
if ($LASTEXITCODE -ne 0) { throw "Gradle build failed with code $LASTEXITCODE" }

$out = Join-Path $PSScriptRoot "app\build\outputs\apk\release\app-release.apk"
if (-not (Test-Path $out)) { throw "APK was not created: $out" }
$dest = Join-Path $PSScriptRoot "RMes-15.1.2.apk"
Copy-Item $out $dest -Force
$aabOut = Join-Path $PSScriptRoot "app\build\outputs\bundle\release\app-release.aab"
$aabDest = Join-Path $PSScriptRoot "RMes-15.1.2.aab"
if (Test-Path $aabOut) { Copy-Item $aabOut $aabDest -Force }
Write-Host "READY APK: $dest" -ForegroundColor Cyan
if (Test-Path $aabDest) { Write-Host "READY AAB: $aabDest" -ForegroundColor Cyan }
