$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$keytool = Get-Command keytool.exe -ErrorAction SilentlyContinue
if ($keytool) {
    $keytoolExe = $keytool.Source
} else {
    $candidate = "C:\Program Files\Android\Android Studio\jbr\bin\keytool.exe"
    if (Test-Path $candidate) { $keytoolExe = $candidate } else { throw "Java keytool not found. Install Android Studio or JDK 17+." }
}
if (Test-Path "rmes-release.jks") { throw "rmes-release.jks already exists. KEEP it: every future APK update must use the same key." }
$store = Read-Host "Create a strong keystore password" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($store)
try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
& $keytoolExe -genkeypair -v -keystore rmes-release.jks -alias rmes -keyalg RSA -keysize 4096 -validity 10000 -storepass $plain -keypass $plain -dname "CN=R-Mes, O=R-Mes, C=UZ"
if ($LASTEXITCODE -ne 0) { throw "keytool failed" }
@"
storeFile=rmes-release.jks
storePassword=$plain
keyAlias=rmes
keyPassword=$plain
"@ | Set-Content -Encoding ASCII keystore.properties
Write-Host "Created signing key. BACK UP rmes-release.jks and keystore.properties securely. Never regenerate the key for an existing installed app." -ForegroundColor Cyan
