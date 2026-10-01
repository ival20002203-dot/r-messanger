param(
    [Parameter(Mandatory=$true)][string]$ServerUrl
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$ServerUrl = $ServerUrl.TrimEnd('/')

$desktop = 'desktop/main.js'
$d = Get-Content $desktop -Raw
$d = [regex]::Replace($d, 'const DEFAULT_URL=.*?;', 'const DEFAULT_URL=process.env.R_MES_URL||"' + $ServerUrl + '";')
Set-Content $desktop $d -Encoding UTF8

$android = 'mobile/android/app/src/main/res/values/strings.xml'
$a = Get-Content $android -Raw
$a = [regex]::Replace($a, '<string name="server_url">.*?</string>', '<string name="server_url">' + $ServerUrl + '</string>')
Set-Content $android $a -Encoding UTF8

$ios = 'mobile/ios/RMesIOS/AppConfig.swift'
$i = Get-Content $ios -Raw
$i = [regex]::Replace($i, 'static let serverURL = URL\(string: ".*?"\)!', 'static let serverURL = URL(string: "' + $ServerUrl + '")!')
Set-Content $ios $i -Encoding UTF8

Write-Host "R-Mes clients now point to $ServerUrl" -ForegroundColor Cyan
