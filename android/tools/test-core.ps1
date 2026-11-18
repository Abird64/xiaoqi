#requires -Version 5.1
# Compile and run the pure-Java core self-tests (no Android, no network).
$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$jdk = if ($env:JAVA_HOME) { $env:JAVA_HOME } else { "C:\Program Files\Java\jdk-17" }
$javac = Join-Path $jdk "bin\javac.exe"
$java = Join-Path $jdk "bin\java.exe"
if (-not (Test-Path $javac)) {
    throw "JDK not found. Set JAVA_HOME or install JDK 17."
}

$out = Join-Path $root "build\test-classes"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$files = @(Get-ChildItem (Join-Path $root "app\src\main\java\com\xiaoqi\steps\core") -Filter *.java |
    ForEach-Object { $_.FullName })
$files += (Join-Path $root "app\src\test\java\com\xiaoqi\steps\core\CoreSelfTest.java")

& $javac --release 11 -encoding UTF-8 -d $out $files
if ($LASTEXITCODE -ne 0) { throw "javac failed" }

& $java "-Dfile.encoding=UTF-8" -cp $out com.xiaoqi.steps.core.CoreSelfTest
exit $LASTEXITCODE
