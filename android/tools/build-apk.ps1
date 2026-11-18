#requires -Version 5.1
<#
  小栖步数 · 离线 APK 构建脚本
  ------------------------------------------------
  不需要 Gradle、不需要联网：直接用 Android SDK 的 aapt2 / d8 / zipalign / apksigner
  把 app/src/main 编成可安装的 APK。

  前置：
    - JDK 17（或 21）
    - Android SDK：platform android-34 + build-tools 34.x
  用法：
    powershell -ExecutionPolicy Bypass -File tools/build-apk.ps1
    powershell ... -VersionName 1.0.1 -VersionCode 2
#>
param(
    [string]$VersionName = "1.0.0",
    [int]$VersionCode = 1,
    [string]$OutputDir = "",
    [string]$PackageName = "com.xiaoqi.steps"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

function Write-Step([string]$text) {
    Write-Host ""
    Write-Host "==> $text" -ForegroundColor Cyan
}

function Find-Jdk {
    $candidates = @()
    if ($env:JAVA_HOME) { $candidates += $env:JAVA_HOME }
    $candidates += "C:\Program Files\Java\jdk-17"
    $candidates += "C:\Program Files\Java\jdk-21"
    $candidates += "C:\Program Files\Eclipse Adoptium\jdk-17"
    foreach ($dir in $candidates) {
        if ($dir -and (Test-Path (Join-Path $dir "bin\javac.exe"))) {
            return (Resolve-Path $dir).Path
        }
    }
    $javac = Get-Command javac.exe -ErrorAction SilentlyContinue
    if ($javac) {
        return (Split-Path (Split-Path $javac.Source -Parent) -Parent)
    }
    throw "找不到 JDK 17+。请安装 JDK 并设置 JAVA_HOME。"
}

function Find-Sdk {
    $candidates = @()
    if ($env:ANDROID_HOME) { $candidates += $env:ANDROID_HOME }
    if ($env:ANDROID_SDK_ROOT) { $candidates += $env:ANDROID_SDK_ROOT }
    $candidates += (Join-Path $env:LOCALAPPDATA "Android\Sdk")
    $candidates += "C:\Android\Sdk"
    foreach ($dir in $candidates) {
        if ($dir -and (Test-Path (Join-Path $dir "platforms")) -and
            (Test-Path (Join-Path $dir "build-tools"))) {
            return (Resolve-Path $dir).Path
        }
    }
    throw "找不到 Android SDK。请设置 ANDROID_HOME 或安装到默认位置。"
}

function Get-BuildTools([string]$sdk) {
    $preferred = Join-Path $sdk "build-tools\34.0.0"
    if (Test-Path (Join-Path $preferred "aapt2.exe")) {
        return (Resolve-Path $preferred).Path
    }
    $found = Get-ChildItem (Join-Path $sdk "build-tools") -Directory |
        Where-Object { Test-Path (Join-Path $_.FullName "aapt2.exe") } |
        Sort-Object { [version]($_.Name -replace "[^0-9.]", "") } -Descending |
        Select-Object -First 1
    if (-not $found) { throw "找不到 build-tools（需要 aapt2.exe）。" }
    return $found.FullName
}

function Get-Platform([string]$sdk) {
    $preferred = Join-Path $sdk "platforms\android-34"
    if (Test-Path (Join-Path $preferred "android.jar")) {
        return (Resolve-Path $preferred).Path
    }
    $found = Get-ChildItem (Join-Path $sdk "platforms") -Directory |
        Where-Object { Test-Path (Join-Path $_.FullName "android.jar") } |
        Sort-Object Name -Descending |
        Select-Object -First 1
    if (-not $found) { throw "找不到 Android platform（需要 android.jar）。" }
    return $found.FullName
}

function Invoke-Checked([string]$exe, [string[]]$arguments, [string]$what) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$what 失败（exit $LASTEXITCODE）"
    }
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$appDir = Join-Path $root "app"
$srcDir = Join-Path $appDir "src\main"
$buildDir = Join-Path $root "build"
$distDir = if ($OutputDir) { $OutputDir } else { Join-Path $root "release" }
$jdk = Find-Jdk
$sdk = Find-Sdk
$buildTools = Get-BuildTools $sdk
$platform = Get-Platform $sdk
$androidJar = Join-Path $platform "android.jar"

$env:JAVA_HOME = $jdk
$env:PATH = (Join-Path $jdk "bin") + ";" + $env:PATH

$aapt2 = Join-Path $buildTools "aapt2.exe"
$d8 = Join-Path $buildTools "d8.bat"
$zipalign = Join-Path $buildTools "zipalign.exe"
$apksigner = Join-Path $buildTools "apksigner.bat"
$keytool = Join-Path $jdk "bin\keytool.exe"

Write-Host "小栖步数 · APK 构建" -ForegroundColor Green
Write-Host "  JDK         : $jdk"
Write-Host "  SDK         : $sdk"
Write-Host "  Build-tools : $buildTools"
Write-Host "  Platform    : $platform"
Write-Host "  Version     : $VersionName ($VersionCode)"

# ---- 清理中间产物（保留签名文件）----
Write-Step "清理中间产物"
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
foreach ($name in @("gen", "classes", "dex", "res.zip", "base.apk",
        "app-unsigned.apk", "app-aligned.apk", "AndroidManifest.xml")) {
    $target = [System.IO.Path]::GetFullPath((Join-Path $buildDir $name))
    if (-not $target.StartsWith([System.IO.Path]::GetFullPath($buildDir),
            [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "拒绝删除构建目录之外的路径：$target"
    }
    if (Test-Path $target) {
        Remove-Item -Recurse -Force $target
    }
}
New-Item -ItemType Directory -Force -Path (Join-Path $buildDir "gen"),
    (Join-Path $buildDir "classes"), (Join-Path $buildDir "dex"),
    $distDir | Out-Null

# ---- 生成带 package 的临时 Manifest（Gradle 工程本身不写 package，交给 namespace）----
Write-Step "准备 Manifest"
$manifestText = Get-Content (Join-Path $srcDir "AndroidManifest.xml") -Raw -Encoding UTF8
if ($manifestText -notmatch "package\s*=") {
    $manifestText = $manifestText -replace "<manifest\s",
        "<manifest package=`"$PackageName`" "
}
$manifestPath = Join-Path $buildDir "AndroidManifest.xml"
Set-Content -Path $manifestPath -Value $manifestText -Encoding UTF8

# ---- 资源 ----
Write-Step "aapt2 compile 资源"
$resDir = Join-Path $srcDir "res"
$resZip = Join-Path $buildDir "res.zip"
Invoke-Checked $aapt2 @("compile", "--dir", $resDir, "-o", $resZip) "aapt2 compile"

Write-Step "aapt2 link 生成基础 APK 与 R.java"
$baseApk = Join-Path $buildDir "base.apk"
$genDir = Join-Path $buildDir "gen"
Invoke-Checked $aapt2 @("link", "-o", $baseApk, "-I", $androidJar,
    "--manifest", $manifestPath, "--min-sdk-version", "26",
    "--target-sdk-version", "34", "--version-code", "$VersionCode",
    "--version-name", $VersionName, "--java", $genDir, $resZip) "aapt2 link"

# ---- Java ----
Write-Step "javac 编译 Java"
$javaFiles = @(Get-ChildItem (Join-Path $srcDir "java") -Recurse -Filter *.java |
    ForEach-Object { $_.FullName })
$javaFiles += @(Get-ChildItem $genDir -Recurse -Filter *.java |
    ForEach-Object { $_.FullName })
Write-Host "  源文件：$($javaFiles.Count) 个"
$classesDir = Join-Path $buildDir "classes"
$javacArgs = @("--release", "11", "-encoding", "UTF-8",
    "-classpath", $androidJar, "-d", $classesDir) + $javaFiles
Invoke-Checked (Join-Path $jdk "bin\javac.exe") $javacArgs "javac"

# ---- dex ----
Write-Step "d8 生成 classes.dex"
$classFiles = @(Get-ChildItem $classesDir -Recurse -Filter *.class |
    ForEach-Object { $_.FullName })
$dexDir = Join-Path $buildDir "dex"
$d8Args = @("--lib", $androidJar, "--min-api", "26", "--output", $dexDir) + $classFiles
Invoke-Checked $d8 $d8Args "d8"
$dexFile = Join-Path $dexDir "classes.dex"
if (-not (Test-Path $dexFile)) { throw "d8 没有生成 classes.dex" }

# ---- 打包 ----
Write-Step "把 classes.dex 放进 APK"
$unsignedApk = Join-Path $buildDir "app-unsigned.apk"
Copy-Item $baseApk $unsignedApk -Force
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::Open(
    $unsignedApk, [System.IO.Compression.ZipArchiveMode]::Update)
try {
    $old = $zip.GetEntry("classes.dex")
    if ($old) { $old.Delete() }
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
        $zip, $dexFile, "classes.dex",
        [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
} finally {
    $zip.Dispose()
}

# ---- 对齐 / 签名 ----
Write-Step "zipalign 对齐"
$alignedApk = Join-Path $buildDir "app-aligned.apk"
Invoke-Checked $zipalign @("-f", "4", $unsignedApk, $alignedApk) "zipalign"

$keystore = Join-Path $buildDir "xiaoqi-debug.keystore"
$storePass = "xiaoqi2026"
$alias = "xiaoqi"
if (-not (Test-Path $keystore)) {
    Write-Step "生成调试签名证书（仅用于演示/侧载）"
    Invoke-Checked $keytool @("-genkeypair", "-keystore", $keystore,
        "-alias", $alias, "-storepass", $storePass, "-keypass", $storePass,
        "-dname", "CN=Xiaoqi Steps, OU=Demo, O=Xiaoqi, L=Shanghai, ST=Shanghai, C=CN",
        "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000") "keytool"
}

$finalApk = Join-Path $distDir "xiaoqi-steps-$VersionName.apk"
if (Test-Path $finalApk) { Remove-Item -Force $finalApk }
Write-Step "apksigner 签名"
Invoke-Checked $apksigner @("sign", "--ks", $keystore, "--ks-key-alias", $alias,
    "--ks-pass", "pass:$storePass", "--key-pass", "pass:$storePass",
    "--out", $finalApk, $alignedApk) "apksigner sign"

# apksigner 默认还会生成 v4 增量签名 .idsig（仅 adb 增量安装用）；侧载不需要，清掉保持交付目录干净。
$idsig = "$finalApk.idsig"
if (Test-Path $idsig) { Remove-Item -Force $idsig }

Write-Step "校验 APK"
Invoke-Checked $apksigner @("verify", "--verbose", "--print-certs", $finalApk) "apksigner verify"
& $aapt2 dump badging $finalApk | Select-Object -First 12

$hash = (Get-FileHash $finalApk -Algorithm SHA256).Hash
$certLine = (& $keytool -list -v -keystore $keystore -alias $alias `
        -storepass $storePass 2>$null | Select-String "SHA256:" |
        Select-Object -First 1)
$cert = if ($certLine) { $certLine.ToString().Trim() } else { "" }
$size = (Get-Item $finalApk).Length
$info = @(
    "小栖步数 Android APK",
    "versionName: $VersionName",
    "versionCode: $VersionCode",
    "package: $PackageName",
    "builtAt: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')",
    "apk: release/xiaoqi-steps-$VersionName.apk",
    "size: $size bytes",
    "sha256: $hash",
    "signing: debug (not for production)",
    "cert: $cert",
    "jdk: $jdk",
    "sdk: $sdk",
    "build-tools: $buildTools"
)
$infoPath = Join-Path $distDir "BUILD-INFO.txt"
Set-Content -Path $infoPath -Value ($info -join "`r`n") -Encoding UTF8

Write-Host ""
Write-Host "BUILD OK" -ForegroundColor Green
Write-Host "  APK    : $finalApk"
Write-Host "  Size   : $size bytes"
Write-Host "  SHA256 : $hash"
Write-Host "  Info   : $infoPath"
