# Experiment 26: high-quality reference videos for all 5 scenes - same output frame counts
# as experiment9b (so "same length"), but with a genuinely higher effective sample count per
# frame (see _bench_video_hq.py's docstring for the two real bugs found and fixed to get
# here: PathTracer's samplesPerPixel hard-cap at 16, and the framerate/autoReset pitfalls of
# multi-subframe accumulation while a QuadLightVideoPlayer is involved).
#
# LSPV=256 (4x experiment9b's 64) + ACCUM_K=8 sub-frames (128 effective samples/pixel vs.
# the ~16 experiment9b's spp=32 actually achieved, silently clamped) per output frame.
#
# Run from repo root: powershell -File results\experiment26\run_reference_hq.ps1 [-OnlyScene <name>]

param(
    [string]$OnlyScene = ''
)

$ErrorActionPreference = 'Stop'
$RepoRoot = "C:\Users\Jose\Desktop\Falcor"
Set-Location $RepoRoot
$Mogwai = "build\windows-vs2022\bin\Release\Mogwai.exe"
$Ffmpeg = "ffmpeg"
$BenchScript = "results\experiment26\_bench_video_hq.py"
$PlaylistDir = "results\experiment26\playlists"
$VideoDir = "results\experiment26\videos"
New-Item -ItemType Directory -Force -Path $VideoDir | Out-Null

$LSPV = 256
$ACCUM_K = 8

# Per-scene: pyscene path, official output frame count (matches experiment9b exactly).
$Scenes = [ordered]@{
    'rover' = @{ Pyscene = 'paperscenes\rover\rover.pyscene'; OutputFrames = 300 }
    'cinema' = @{ Pyscene = 'paperscenes\cinema\cinema.pyscene'; OutputFrames = 251 }
    'fireplace_room' = @{ Pyscene = 'paperscenes\fireplace_room\fireplace_room.pyscene'; OutputFrames = 300 }
    'convergence' = @{ Pyscene = 'paperscenes\convergence\convergence.pyscene'; OutputFrames = 637 }
    'phonehand' = @{ Pyscene = 'paperscenes\phonehand\phonehand.pyscene'; OutputFrames = 1199 }
}
if ($OnlyScene) {
    $filtered = [ordered]@{}
    foreach ($k in $Scenes.Keys) { if ($k -eq $OnlyScene) { $filtered[$k] = $Scenes[$k] } }
    $Scenes = $filtered
}

function New-SceneVariantPlaylist($pysceneRelPath, $playlistPathAbs, $tag) {
    $pysceneFullPath = Join-Path $RepoRoot $pysceneRelPath
    $dir = Split-Path $pysceneFullPath -Parent
    $content = Get-Content $pysceneFullPath -Raw
    $escaped = $playlistPathAbs.Replace('\', '/')
    $pattern = "'\.\./\.\./quadlight/[^']+\.hdr'"
    $newContent = [Regex]::Replace($content, $pattern, "'$escaped'")
    $variantPath = Join-Path $dir "_e26ref_$tag.pyscene"
    Set-Content -Path $variantPath -Value $newContent -NoNewline
    return $variantPath
}

function Invoke-Encode {
    param([string]$FrameDir, [string]$FramePattern, [string]$OutMp4, [string]$OutWebm, [int]$Fps)
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $Ffmpeg -y -framerate $Fps -i (Join-Path $FrameDir $FramePattern) -c:v libx264 -pix_fmt yuv420p -crf 18 -preset slow $OutMp4 2>$null | Out-Null
    & $Ffmpeg -y -framerate $Fps -i (Join-Path $FrameDir $FramePattern) -c:v libvpx-vp9 -pix_fmt yuv420p -crf 30 -b:v 0 $OutWebm 2>$null | Out-Null
    $ErrorActionPreference = $prevEap
    if (-not (Test-Path $OutMp4)) { throw "ffmpeg failed to produce $OutMp4" }
    if (-not (Test-Path $OutWebm)) { throw "ffmpeg failed to produce $OutWebm" }
}

foreach ($sceneName in $Scenes.Keys) {
  try {
    $sceneDef = $Scenes[$sceneName]
    $outFrames = $sceneDef.OutputFrames
    Write-Host "`n`n########## Scene: $sceneName ($outFrames output frames x K=$ACCUM_K = $($outFrames*$ACCUM_K) raw sub-frames) ##########"
    $t0 = Get-Date

    $playlistPath = Join-Path $RepoRoot "$PlaylistDir\${sceneName}_full_hq_k${ACCUM_K}.hdrplaylist"
    $variantScene = New-SceneVariantPlaylist $sceneDef.Pyscene $playlistPath $sceneName

    try {
        $frameOutDir = Join-Path $RepoRoot "results\experiment26\_frames_${sceneName}_ref"
        New-Item -ItemType Directory -Force -Path $frameOutDir | Out-Null

        $env:BENCH_LSPV = "$LSPV"
        $env:BENCH_ACCUM_K = "$ACCUM_K"
        $env:BENCH_OUTPUT_FRAMES = "$outFrames"
        $env:BENCH_OUT_DIR = $frameOutDir
        $env:BENCH_OUT_NAME = 'f'
        $logPath = Join-Path $frameOutDir 'render.log'
        $procArgs = @("--headless", "-s", $BenchScript, "-S", $variantScene, "-l", $logPath, "-v", "2")
        $p = Start-Process -FilePath $Mogwai -ArgumentList $procArgs -WorkingDirectory $RepoRoot -Wait -PassThru -NoNewWindow
        if ($p.ExitCode -ne 0) {
            Write-Warning "  Render failed (exit $($p.ExitCode)) $sceneName - see $logPath"
            continue
        }

        $captured = Get-ChildItem -Path $frameOutDir -Filter "f.ToneMapper.dst.*.png" | Sort-Object { [int]([regex]::Match($_.Name, '\d+').Value) }
        $seq = 0
        foreach ($file in $captured) {
            $seq++
            $newName = "f{0:D4}.png" -f $seq
            Rename-Item -Path $file.FullName -NewName $newName -Force
        }
        Write-Host "  $seq frames captured (expected $outFrames)"

        if ($seq -eq 0) { Write-Warning "  No frames captured for $sceneName - skipping encode"; Remove-Item -Recurse -Force $frameOutDir -ErrorAction SilentlyContinue; continue }

        $mp4Path = Join-Path $RepoRoot "$VideoDir\${sceneName}_reference_hq.mp4"
        $webmPath = Join-Path $RepoRoot "$VideoDir\${sceneName}_reference_hq.webm"
        Write-Host "  Encoding -> $mp4Path / $webmPath"
        Invoke-Encode -FrameDir $frameOutDir -FramePattern 'f%04d.png' -OutMp4 $mp4Path -OutWebm $webmPath -Fps 24

        # Clean up raw PNGs IMMEDIATELY after encoding - critical for staying under the 10GB
        # budget, since this scene's raw frames alone can be several GB (e.g. convergence at
        # 3840x2160 x 637 frames).
        Remove-Item -Recurse -Force $frameOutDir -ErrorAction SilentlyContinue

        $elapsed = (Get-Date) - $t0
        Write-Host "  Scene $sceneName done in $($elapsed.ToString('hh\:mm\:ss'))"
        $videoBytes = (Get-ChildItem $VideoDir | Measure-Object -Property Length -Sum).Sum
        Write-Host "  Cumulative videos/ size so far: $([math]::Round($videoBytes/1GB, 3)) GB"
    }
    finally {
        if (Test-Path $variantScene) { Remove-Item $variantScene -Force -ErrorAction SilentlyContinue }
    }
  }
  catch {
    Write-Host "`n!!!!!!!!!! FAILED scene $sceneName !!!!!!!!!!"
    Write-Host "Exception: $($_.Exception.ToString())"
  }
}

Write-Host "`n`n=== Experiment 26 (high-quality reference videos) done ==="
Get-ChildItem $VideoDir | Format-Table Name, Length -AutoSize
