# Experiment 26: camera flythrough videos, our technique only, denoiser on. Camera does a
# smooth azimuthal swing (+/-8 deg around each scene's own original viewing angle) plus a
# gentle rise-and-fall (+12% height at the midpoint), ONE full sweep-and-return cycle spread
# across the WHOLE flythrough (all loops) - a single graceful continuous motion, not one
# cycle per loop.
#
# Per your request: each scene's flythrough covers its own FULL native frame count (every
# frame of that scene's actual HDR video sequence, not an arbitrary fixed length), looped
# $LoopCount times - QuadLightVideoPlayer loops its playlist natively (index = sequence %
# playlist.size(), confirmed by reading QuadLightVideo.cpp), so requesting
# NativeFrames*LoopCount total frames just plays the real content through that many times
# automatically; no special playlist authoring needed.
#
# Amplitude validated via pilot (see SUMMARY.md): a larger initial guess (35 deg sweep, 40%
# rise) revealed Rover's LED wall panel edges (a real, scene-specific limitation - it's a
# finite virtual-production panel, not an infinite backdrop); this conservative amplitude
# was confirmed clean on rover (worst case), convergence (enclosed room), and phonehand
# (close-up) pilots.
#
# phonehand is deliberately excluded, same as experiment9b's own denoised set - experiment8
# found denoising hurts phonehand specifically.
#
# Run from repo root: powershell -File results\experiment26\run_flythrough.ps1 [-OnlyScene <name>]

param(
    [string]$OnlyScene = ''
)

$ErrorActionPreference = 'Stop'
$RepoRoot = "C:\Users\Jose\Desktop\Falcor"
Set-Location $RepoRoot
$Mogwai = "build\windows-vs2022\bin\Release\Mogwai.exe"
$Ffmpeg = "ffmpeg"
$BenchScript = "results\experiment26\_bench_flythrough.py"
$PlaylistDir = "results\experiment26\playlists"
$VideoDir = "results\experiment26\videos"
New-Item -ItemType Directory -Force -Path $VideoDir | Out-Null

$LoopCount = 2  # "a couple of times" through each scene's own full native sequence
$WarmupFrames = 4
$SweepDeg = 8
$RiseFrac = 0.12
$Fps = 24

# Per-scene: pyscene, native frame count (matches each scene's official quadlight family -
# same values gen_playlists.py / experiment9b use), official calibrated "ours" config.
$Scenes = [ordered]@{
    'rover' = @{ Pyscene = 'paperscenes\rover\rover.pyscene'; NativeFrames = 300
        Ours = @{ Sampler = 'BudgetLeafAlias'; Spp = 4; Lspv = 22; LeafBudget = 4000 } }
    'cinema' = @{ Pyscene = 'paperscenes\cinema\cinema.pyscene'; NativeFrames = 251
        Ours = @{ Sampler = 'AliasCtu'; Spp = 4; Lspv = 8; LeafBudget = 0 } }
    'fireplace_room' = @{ Pyscene = 'paperscenes\fireplace_room\fireplace_room.pyscene'; NativeFrames = 300
        Ours = @{ Sampler = 'AliasCtu'; Spp = 4; Lspv = 4; LeafBudget = 0 } }
    'convergence' = @{ Pyscene = 'paperscenes\convergence\convergence.pyscene'; NativeFrames = 637
        Ours = @{ Sampler = 'AliasCtu'; Spp = 4; Lspv = 3; LeafBudget = 0 } }
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
    $variantPath = Join-Path $dir "_e26fly_$tag.pyscene"
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
    $FlythroughFrames = $sceneDef.NativeFrames * $LoopCount
    Write-Host "`n`n########## Scene: $sceneName flythrough ($($sceneDef.NativeFrames) native frames x $LoopCount loops = $FlythroughFrames frames) ##########"
    $t0 = Get-Date

    $playlistPath = Join-Path $RepoRoot "$PlaylistDir\${sceneName}_full.hdrplaylist"
    $variantScene = New-SceneVariantPlaylist $sceneDef.Pyscene $playlistPath $sceneName

    try {
        $frameOutDir = Join-Path $RepoRoot "results\experiment26\_frames_${sceneName}_fly"
        New-Item -ItemType Directory -Force -Path $frameOutDir | Out-Null

        $cfg = $sceneDef.Ours
        $env:BENCH_SAMPLER = $cfg.Sampler
        $env:BENCH_SPP = "$($cfg.Spp)"
        $env:BENCH_LSPV = "$($cfg.Lspv)"
        $env:BENCH_LEAF_BUDGET = "$($cfg.LeafBudget)"
        $env:BENCH_TOTAL_FRAMES = "$FlythroughFrames"
        $env:BENCH_WARMUP_FRAMES = "$WarmupFrames"
        $env:BENCH_SWEEP_DEG = "$SweepDeg"
        $env:BENCH_RISE_FRAC = "$RiseFrac"
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
        Write-Host "  $seq frames captured (expected $($FlythroughFrames - $WarmupFrames))"

        if ($seq -eq 0) { Write-Warning "  No frames captured for $sceneName - skipping encode"; Remove-Item -Recurse -Force $frameOutDir -ErrorAction SilentlyContinue; continue }

        $mp4Path = Join-Path $RepoRoot "$VideoDir\${sceneName}_flythrough_denoised.mp4"
        $webmPath = Join-Path $RepoRoot "$VideoDir\${sceneName}_flythrough_denoised.webm"
        Write-Host "  Encoding -> $mp4Path / $webmPath"
        Invoke-Encode -FrameDir $frameOutDir -FramePattern 'f%04d.png' -OutMp4 $mp4Path -OutWebm $webmPath -Fps $Fps

        Remove-Item -Recurse -Force $frameOutDir -ErrorAction SilentlyContinue

        $elapsed = (Get-Date) - $t0
        Write-Host "  Scene $sceneName flythrough done in $($elapsed.ToString('hh\:mm\:ss'))"
        $videoBytes = (Get-ChildItem $VideoDir | Measure-Object -Property Length -Sum).Sum
        Write-Host "  Cumulative videos/ size so far: $([math]::Round($videoBytes/1GB, 3)) GB"
    }
    finally {
        if (Test-Path $variantScene) { Remove-Item $variantScene -Force -ErrorAction SilentlyContinue }
    }
  }
  catch {
    Write-Host "`n!!!!!!!!!! FAILED scene $sceneName flythrough !!!!!!!!!!"
    Write-Host "Exception: $($_.Exception.ToString())"
  }
}

Write-Host "`n`n=== Experiment 26 (flythrough videos) done ==="
Get-ChildItem $VideoDir | Format-Table Name, Length -AutoSize
