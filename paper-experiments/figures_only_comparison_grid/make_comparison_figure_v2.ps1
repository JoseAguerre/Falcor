# v2 (experiment22, ReSTIR Fig.8-style rework of results/make_comparison_figure.ps1 - this is
# a copy, the original is untouched): builds a paper-style comparison figure for one scene:
#   - Top: the scene split into 4 DIAGONAL bands, each rendered with a different technique
#     (Random | 2D CDF | best-of-ours | Reference), thick divider lines, 2 colored squares
#     (red, yellow) marking the 2 chosen closeup regions.
#   - Bottom: 2 rows of 4 closeups (one row per marked region, border-colored to match its
#     square), each row showing Random / 2D CDF / ours / Reference at that region, at a much
#     larger UpscaleTo than the original 4-region version so each crop reads clearly.
#
# Closeup regions are chosen to maximize (errCdf - errOurs) specifically - i.e. the regions
# where OUR technique visibly beats 2D CDF the most (not just beats Random) - since 2D CDF
# is the more relevant baseline. Unlike the original script (one best region PER diagonal
# band), this version scores candidate windows across the WHOLE image and greedily keeps the
# top $MaxRegions (default 2) subject to a minimum center-to-center distance - matching how
# ReSTIR's own Fig.8 picks its 2 closeups from wherever the difference is clearest, not tied
# to a specific quadrant of the image. Error = mean absolute per-channel difference vs
# reference, via LockBits raw byte access (fast).
#
# Usage: powershell -File make_comparison_figure_v2.ps1 -SceneDir <dir> -SceneName <name> -OursLabel <label> -OursDisplayName <name> -OutPath <path>

param(
    [Parameter(Mandatory=$true)][string]$SceneDir,
    [Parameter(Mandatory=$true)][string]$SceneName,
    [Parameter(Mandatory=$true)][string]$OursLabel,
    [string]$OursDisplayName = '',
    [Parameter(Mandatory=$true)][string]$OutPath,
    [int]$CropSize = 50,
    [int]$UpscaleTo = 300,
    [int]$DiagonalShift = 220,
    [int]$DividerWidth = 5,
    # Optional manual overrides for specific regions - keys are region index strings ("0","1",
    # ...), values @{X=;Y=} top-left crop coords. Bypasses the automatic search for that
    # region only (used when the auto-picked spot landed somewhere visually uninteresting).
    [hashtable]$ManualRegions = @{},
    # v2 (experiment22 figures-only-page rework, ReSTIR Fig.8 style): pick the best
    # $MaxRegions windows GLOBALLY by (errCdf - errOurs) score across the WHOLE image,
    # instead of one-per-diagonal-band - ReSTIR's own Fig.8 picks 2 closeups per scene from
    # wherever the difference is clearest, not tied to a specific quadrant. A minimum
    # center-to-center distance keeps the chosen regions from clustering together.
    [int]$MaxRegions = 2,
    [int]$MinRegionDistance = 150,
    # Optional real measured metrics to print under each label (ReSTIR Fig.8 shows RMAE under
    # the top labels and Time under the closeup labels) - keys "Random","Cdf2D","Ours", each
    # value a hashtable @{Rmse=<double>; Ms=<double>}. Left empty, no metric lines are drawn
    # (matches the original script's plain-label behavior).
    [hashtable]$Metrics = @{},
    # v5 (experiment22 figures-only-page, round 2): revert region SELECTION to the original
    # script's one-per-diagonal-band scheme (classic Yellow/Cyan/Magenta/Orange colors tied
    # to band index 0=Random/1=Cdf2D/2=Ours/3=Reference) instead of v2's global-top-N search,
    # so specific "the original purple+yellow region" style requests can be honored by band
    # index. Combine with -KeepBands to draw only some of the 4.
    [switch]$PerBand,
    # Which of the 4 band-tied regions to actually draw (default: all 4). e.g. @(2,0) keeps
    # only the Ours(Magenta) and Random(Yellow) regions. Only used when -PerBand is set.
    [int[]]$KeepBands = @(0, 1, 2, 3),
    # v5: suppress the "Time: x.xms" line under closeup labels (RMSE under the top labels is
    # kept) - the per-crop render time wasn't judged useful.
    [switch]$NoTime,
    # v5: instead of a separate white label bar/strip, draw larger white (outlined for
    # legibility) text directly ON TOP of the image content - ReSTIR Fig.8's own convention.
    [switch]$OverlayLabels
)

Add-Type -AssemblyName System.Drawing
$ErrorActionPreference = 'Stop'
if (-not $OursDisplayName) { $OursDisplayName = $OursLabel }

# v5: white text directly over image content (ReSTIR Fig.8 style) needs a dark outline to
# stay legible over bright image regions - drawn as 4 offset black copies behind a white one.
function Draw-OutlinedString($g, $text, $font, $rect, $sf) {
    $black = [System.Drawing.Brushes]::Black
    $white = [System.Drawing.Brushes]::White
    foreach ($d in @(@(-1,-1), @(1,-1), @(-1,1), @(1,1), @(0,-1), @(0,1), @(-1,0), @(1,0))) {
        $r2 = New-Object System.Drawing.RectangleF(($rect.X + $d[0]), ($rect.Y + $d[1]), $rect.Width, $rect.Height)
        $g.DrawString($text, $font, $black, $r2, $sf)
    }
    $g.DrawString($text, $font, $white, $rect, $sf)
}

function Find-Png($dir, $prefix) {
    # Sort by LastWriteTime descending - Get-ChildItem's default alphabetical order can rank a
    # stale reference.*.<oldframecount>.png ahead of a freshly-rendered one (e.g. "14332" sorts
    # before "14400"), silently comparing against a leftover file from a previous run.
    $f = Get-ChildItem -Path $dir -Filter "$prefix.*.png" -ErrorAction SilentlyContinue | Where-Object { $_.Name -notlike "*heatmap*" -and $_.Name -notlike "*errorMap*" } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $f) { throw "No PNG found for prefix '$prefix' in $dir" }
    return $f.FullName
}

$randomPath = Find-Png $SceneDir 'Random'
$cdf2dPath = Find-Png $SceneDir 'Cdf2D'
$oursPath = Find-Png $SceneDir $OursLabel
$refPath = Find-Png $SceneDir 'reference'

Write-Host "Random: $randomPath"
Write-Host "Cdf2D: $cdf2dPath"
Write-Host "Ours ($OursLabel): $oursPath"
Write-Host "Reference: $refPath"

function Get-RawBytes($path) {
    $bmp = [System.Drawing.Bitmap]::FromFile($path)
    $rect = New-Object System.Drawing.Rectangle(0, 0, $bmp.Width, $bmp.Height)
    $data = $bmp.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $bytes = New-Object byte[] ($data.Stride * $bmp.Height)
    [System.Runtime.InteropServices.Marshal]::Copy($data.Scan0, $bytes, 0, $bytes.Length)
    $bmp.UnlockBits($data)
    return @{ Bitmap = $bmp; Bytes = $bytes; Stride = $data.Stride; Width = $bmp.Width; Height = $bmp.Height }
}

$refImg = Get-RawBytes $refPath
$randImg = Get-RawBytes $randomPath
$cdfImg = Get-RawBytes $cdf2dPath
$oursImg = Get-RawBytes $oursPath

$W = $refImg.Width
$H = $refImg.Height
$stride = $refImg.Stride
Write-Host "Image size: ${W}x${H}"

function Window-Error($img, $ref, $x0, $y0, $size) {
    $sum = 0.0; $count = 0
    for ($y = $y0; $y -lt ($y0 + $size); $y += 2) {
        $rowOff = $y * $img.Stride; $refRowOff = $y * $ref.Stride
        for ($x = $x0; $x -lt ($x0 + $size); $x += 2) {
            $o = $rowOff + $x * 4; $ro = $refRowOff + $x * 4
            $db = [double]$img.Bytes[$o] - [double]$ref.Bytes[$ro]
            $dg = [double]$img.Bytes[$o+1] - [double]$ref.Bytes[$ro+1]
            $dr = [double]$img.Bytes[$o+2] - [double]$ref.Bytes[$ro+2]
            $sum += [Math]::Abs($db) + [Math]::Abs($dg) + [Math]::Abs($dr)
            $count++
        }
    }
    if ($count -eq 0) { return 0.0 }
    return $sum / $count
}

function Window-RefBrightness($ref, $x0, $y0, $size) {
    $sum = 0.0; $count = 0
    for ($y = $y0; $y -lt ($y0 + $size); $y += 3) {
        $rowOff = $y * $ref.Stride
        for ($x = $x0; $x -lt ($x0 + $size); $x += 3) {
            $o = $rowOff + $x * 4
            $sum += ([double]$ref.Bytes[$o] + [double]$ref.Bytes[$o+1] + [double]$ref.Bytes[$o+2]) / 3.0
            $count++
        }
    }
    if ($count -eq 0) { return 0.0 }
    return $sum / $count
}

function Window-RefVariance($ref, $x0, $y0, $size) {
    # Local luminance variance in the REFERENCE - used to reject flat/featureless regions
    # (e.g. a plain floor) that can still score well on raw error but don't visually
    # demonstrate anything, since there's no real detail there to lose in the first place.
    $sum = 0.0; $sumSq = 0.0; $count = 0
    for ($y = $y0; $y -lt ($y0 + $size); $y += 2) {
        $rowOff = $y * $ref.Stride
        for ($x = $x0; $x -lt ($x0 + $size); $x += 2) {
            $o = $rowOff + $x * 4
            $lum = ([double]$ref.Bytes[$o] + [double]$ref.Bytes[$o+1] + [double]$ref.Bytes[$o+2]) / 3.0
            $sum += $lum; $sumSq += $lum * $lum; $count++
        }
    }
    if ($count -eq 0) { return 0.0 }
    $mean = $sum / $count
    return ($sumSq / $count) - ($mean * $mean)
}

# --- Build the 4-way DIAGONAL split composite via raw byte row-segment copy ---
# (Boundaries are computed FIRST now - the closeup search below is restricted per-band to
# each of these 4 diagonal regions, one closeup per band, instead of free-floating search.)
$destBytes = New-Object byte[] ($refImg.Bytes.Length)
$boundaries = New-Object 'int[,]' ($H, 3)
for ($y = 0; $y -lt $H; $y++) {
    $t = if ($H -gt 1) { $y / [double]($H - 1) } else { 0.0 }
    $shift = [int](($t - 0.5) * $DiagonalShift)
    $b1 = [Math]::Max(0, [Math]::Min($W, [int]($W / 4) + $shift))
    $b2 = [Math]::Max(0, [Math]::Min($W, [int]($W / 2) + $shift))
    $b3 = [Math]::Max(0, [Math]::Min($W, [int]($W * 3 / 4) + $shift))
    $boundaries[$y, 0] = $b1; $boundaries[$y, 1] = $b2; $boundaries[$y, 2] = $b3

    $rowOff = $y * $stride
    if ($b1 -gt 0) { [Array]::Copy($randImg.Bytes, $rowOff, $destBytes, $rowOff, $b1 * 4) }
    if ($b2 -gt $b1) { [Array]::Copy($cdfImg.Bytes, $rowOff + $b1 * 4, $destBytes, $rowOff + $b1 * 4, ($b2 - $b1) * 4) }
    if ($b3 -gt $b2) { [Array]::Copy($oursImg.Bytes, $rowOff + $b2 * 4, $destBytes, $rowOff + $b2 * 4, ($b3 - $b2) * 4) }
    if ($W -gt $b3) { [Array]::Copy($refImg.Bytes, $rowOff + $b3 * 4, $destBytes, $rowOff + $b3 * 4, ($W - $b3) * 4) }
}

function Get-BandAt($x, $y) {
    # Which of the 4 diagonal bands (0=Random,1=Cdf2D,2=Ours,3=Reference) a point falls in,
    # using this row's own boundaries (they shift per-row for the diagonal slant).
    $yy = [Math]::Max(0, [Math]::Min(($H - 1), $y))
    if ($x -lt $boundaries[$yy, 0]) { return 0 }
    if ($x -lt $boundaries[$yy, 1]) { return 1 }
    if ($x -lt $boundaries[$yy, 2]) { return 2 }
    return 3
}

# --- Region selection: either PerBand (classic, one region per diagonal band, original
# script's behavior) or the v2 global-top-N search. ---
$margin = [int]($CropSize * 0.6)
$scanStride = 16

if ($PerBand) {
    $bandCandidates = @(@(), @(), @(), @())
    for ($y0 = $margin; $y0 -le ($H - $CropSize - $margin); $y0 += $scanStride) {
        for ($x0 = $margin; $x0 -le ($W - $CropSize - $margin); $x0 += $scanStride) {
            $cx = $x0 + [int]($CropSize / 2); $cy = $y0 + [int]($CropSize / 2)
            $band = Get-BandAt $cx $cy
            $brightness = Window-RefBrightness $refImg $x0 $y0 $CropSize
            if ($brightness -lt 8) { continue }
            $variance = Window-RefVariance $refImg $x0 $y0 $CropSize
            if ($variance -lt 120) { continue }
            $errCdf = Window-Error $cdfImg $refImg $x0 $y0 $CropSize
            $errOurs = Window-Error $oursImg $refImg $x0 $y0 $CropSize
            $bandCandidates[$band] += [PSCustomObject]@{ Band = $band; X = $x0; Y = $y0; ErrCdf = $errCdf; ErrOurs = $errOurs; Score = ($errCdf - $errOurs) }
        }
    }
    $bandNames = @("Random", "2D CDF", $OursDisplayName, "Reference")
    $chosen = @()
    for ($b = 0; $b -lt 4; $b++) {
        if ($KeepBands -notcontains $b) { continue }
        # Manual override keyed by BAND INDEX (e.g. "2" = the Ours/Magenta band) - lets a
        # specific band's region be hand-placed instead of auto-picked (v6: moving Phone's
        # Magenta closeup onto the other hand).
        if ($ManualRegions.ContainsKey("$b")) {
            $mx = [int]$ManualRegions["$b"].X; $my = [int]$ManualRegions["$b"].Y
            $errCdf = Window-Error $cdfImg $refImg $mx $my $CropSize
            $errOurs = Window-Error $oursImg $refImg $mx $my $CropSize
            $manual = [PSCustomObject]@{ Band = $b; X = $mx; Y = $my; ErrCdf = $errCdf; ErrOurs = $errOurs; Score = ($errCdf - $errOurs) }
            $chosen += $manual
            Write-Host ("Band {0} ({1}, MANUAL): x={2} y={3} (errCdf={4:N2} errOurs={5:N2} score={6:N2})" -f $b, $bandNames[$b], $manual.X, $manual.Y, $manual.ErrCdf, $manual.ErrOurs, $manual.Score)
            continue
        }
        if ($bandCandidates[$b].Count -eq 0) {
            Write-Warning "No valid candidate found in the '$($bandNames[$b])' band."
            continue
        }
        $best = $bandCandidates[$b] | Sort-Object -Property Score -Descending | Select-Object -First 1
        $chosen += $best
        Write-Host ("Band {0} ({1}): x={2} y={3} (errCdf={4:N2} errOurs={5:N2} score={6:N2})" -f $b, $bandNames[$b], $best.X, $best.Y, $best.ErrCdf, $best.ErrOurs, $best.Score)
    }
    # Classic per-band colors: Yellow=Random(0), Cyan=Cdf2D(1), Magenta=Ours(2), Orange=Reference(3)
    $allMarkerColors = @([System.Drawing.Color]::Yellow, [System.Drawing.Color]::Cyan, [System.Drawing.Color]::Magenta, [System.Drawing.Color]::Orange)
    $markerColors = @()
    foreach ($r in $chosen) { $markerColors += $allMarkerColors[$r.Band] }
}
else {
    $allCandidates = @()
    for ($y0 = $margin; $y0 -le ($H - $CropSize - $margin); $y0 += $scanStride) {
        for ($x0 = $margin; $x0 -le ($W - $CropSize - $margin); $x0 += $scanStride) {
            $brightness = Window-RefBrightness $refImg $x0 $y0 $CropSize
            if ($brightness -lt 8) { continue }
            $variance = Window-RefVariance $refImg $x0 $y0 $CropSize
            if ($variance -lt 120) { continue }

            $errCdf = Window-Error $cdfImg $refImg $x0 $y0 $CropSize
            $errOurs = Window-Error $oursImg $refImg $x0 $y0 $CropSize
            $score = $errCdf - $errOurs

            $allCandidates += [PSCustomObject]@{ X = $x0; Y = $y0; ErrCdf = $errCdf; ErrOurs = $errOurs; Score = $score }
        }
    }

    $chosen = @()
    for ($r = 0; $r -lt $MaxRegions; $r++) {
        if ($ManualRegions.ContainsKey("$r")) {
            $mx = [int]$ManualRegions["$r"].X; $my = [int]$ManualRegions["$r"].Y
            $errCdf = Window-Error $cdfImg $refImg $mx $my $CropSize
            $errOurs = Window-Error $oursImg $refImg $mx $my $CropSize
            $manual = [PSCustomObject]@{ X = $mx; Y = $my; ErrCdf = $errCdf; ErrOurs = $errOurs; Score = ($errCdf - $errOurs) }
            $chosen += $manual
            Write-Host ("Region {0} (MANUAL): x={1} y={2} (errCdf={3:N2} errOurs={4:N2} score={5:N2})" -f ($r+1), $manual.X, $manual.Y, $manual.ErrCdf, $manual.ErrOurs, $manual.Score)
            continue
        }
        $sorted = $allCandidates | Sort-Object -Property Score -Descending
        $pick = $null
        foreach ($cand in $sorted) {
            $tooClose = $false
            foreach ($existing in $chosen) {
                $dx = ($cand.X + $CropSize/2) - ($existing.X + $CropSize/2)
                $dy = ($cand.Y + $CropSize/2) - ($existing.Y + $CropSize/2)
                if ([Math]::Sqrt($dx*$dx + $dy*$dy) -lt $MinRegionDistance) { $tooClose = $true; break }
            }
            if (-not $tooClose) { $pick = $cand; break }
        }
        if ($null -eq $pick) {
            Write-Warning "Could not find a $($r+1)-th region far enough from the others - skipping."
            continue
        }
        $chosen += $pick
        Write-Host ("Region {0}: x={1} y={2} (errCdf={3:N2} errOurs={4:N2} score={5:N2})" -f ($r+1), $pick.X, $pick.Y, $pick.ErrCdf, $pick.ErrOurs, $pick.Score)
    }

    # ReSTIR Fig.8's own two-region marker convention: red for the first (strongest) region,
    # yellow for the second.
    $markerColors = @([System.Drawing.Color]::Red, [System.Drawing.Color]::FromArgb(255, 220, 0))
}

$splitBmp = New-Object System.Drawing.Bitmap($W, $H)
$splitRect = New-Object System.Drawing.Rectangle(0, 0, $W, $H)
$splitData = $splitBmp.LockBits($splitRect, [System.Drawing.Imaging.ImageLockMode]::WriteOnly, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
[System.Runtime.InteropServices.Marshal]::Copy($destBytes, 0, $splitData.Scan0, $destBytes.Length)
$splitBmp.UnlockBits($splitData)

# --- Compose final: label bar (or overlay) + split image (with divider lines + markers) ---
$hasMetrics = $Metrics.Count -gt 0
$showTime = $hasMetrics -and (-not $NoTime)
$labelHeight = if ($OverlayLabels) { 0 } elseif ($hasMetrics) { 64 } else { 44 }
$compositeH = $H + $labelHeight
$composite = New-Object System.Drawing.Bitmap($W, $compositeH)
$g = [System.Drawing.Graphics]::FromImage($composite)
$g.Clear([System.Drawing.Color]::White)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
$g.DrawImage($splitBmp, 0, $labelHeight)

# Thick diagonal divider lines (2x the original 2px straight-line width -> 5px)
$pen = New-Object System.Drawing.Pen([System.Drawing.Color]::White, $DividerWidth)
for ($b = 0; $b -lt 3; $b++) {
    $topX = $boundaries[0, $b]
    $botX = $boundaries[($H - 1), $b]
    $g.DrawLine($pen, $topX, $labelHeight, $botX, $compositeH)
}

# Labels (centered over each band's horizontal position), with an optional 2nd line showing
# that technique's real measured RMSE (ReSTIR Fig.8's own "RMAE: x.xx" convention).
# v7: bigger fonts again; -OverlayLabels draws them in white, outlined, directly on the image
# instead of reserving a separate white bar. StringFormat gets NoClip so a font bump never
# silently clips glyphs against a layout rectangle sized for a smaller font (v6's closeup
# labels were getting cut off the top for exactly this reason).
$mainFontSize = if ($OverlayLabels) { 30 } else { 15 }
$metricFontSize = if ($OverlayLabels) { 24 } else { 13 }
$font = New-Object System.Drawing.Font("Arial", $mainFontSize, [System.Drawing.FontStyle]::Bold)
$metricFont = New-Object System.Drawing.Font("Arial", $metricFontSize, [System.Drawing.FontStyle]::Regular)
$brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::Black)
if (-not $OverlayLabels) {
    $bgBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
    $g.FillRectangle($bgBrush, 0, 0, $W, $labelHeight)
}
$sf = New-Object System.Drawing.StringFormat
$sf.Alignment = [System.Drawing.StringAlignment]::Center
$sf.FormatFlags = [System.Drawing.StringFormatFlags]::NoClip
# v7: the label text sits near the TOP of the photo (y~10-80), where the diagonal bands are
# shifted noticeably left of their midY position (shift = (t-0.5)*DiagonalShift, so at y=0 the
# shift is -DiagonalShift/2 rather than 0) - centering with midY's boundaries put the overlaid
# text ~100px off from the actual diagonal lines visible right next to it. Use the boundary at
# the label zone's own y instead so the text is centered between the REAL nearby diagonal
# lines, not the ones at the vertical middle of the whole image.
$labelZoneY = if ($OverlayLabels) { 45 } else { [int]($H / 2) }
$mb1 = $boundaries[$labelZoneY, 0]; $mb2 = $boundaries[$labelZoneY, 1]; $mb3 = $boundaries[$labelZoneY, 2]
$labelCols = @(
    @{ Name = "Random"; X0 = 0; X1 = $mb1; Key = "Random" },
    @{ Name = "2D CDF"; X0 = $mb1; X1 = $mb2; Key = "Cdf2D" },
    @{ Name = $OursDisplayName; X0 = $mb2; X1 = $mb3; Key = "Ours" },
    @{ Name = "Reference"; X0 = $mb3; X1 = $W; Key = $null }
)
$nameY = if ($OverlayLabels) { 10 } else { 8 }
$rmseY = if ($OverlayLabels) { 52 } else { 34 }
foreach ($col in $labelCols) {
    $colW = $col.X1 - $col.X0
    $nameRect = New-Object System.Drawing.RectangleF($col.X0, $nameY, $colW, 30)
    if ($OverlayLabels) { Draw-OutlinedString $g $col.Name $font $nameRect $sf }
    else { $g.DrawString($col.Name, $font, $brush, $nameRect, $sf) }
    if ($hasMetrics -and $col.Key -and $Metrics.ContainsKey($col.Key)) {
        $rmse = $Metrics[$col.Key].Rmse
        $rmseRect = New-Object System.Drawing.RectangleF($col.X0, $rmseY, $colW, 24)
        $rmseText = "RMSE: {0:N4}" -f $rmse
        if ($OverlayLabels) { Draw-OutlinedString $g $rmseText $metricFont $rmseRect $sf }
        else { $g.DrawString($rmseText, $metricFont, $brush, $rmseRect, $sf) }
    }
}

# Colored marker squares at the chosen regions (color tied to selection order/band)
for ($i = 0; $i -lt $chosen.Count; $i++) {
    $markerPen = New-Object System.Drawing.Pen($markerColors[$i % $markerColors.Count], $DividerWidth)
    $g.DrawRectangle($markerPen, $chosen[$i].X, ($chosen[$i].Y + $labelHeight), $CropSize, $CropSize)
}

# --- Closeup rows: one per chosen region, 4 crops each (Random / 2D CDF / Ours / Reference) ---
$srcRandom = [System.Drawing.Bitmap]::FromFile($randomPath)
$srcCdf = [System.Drawing.Bitmap]::FromFile($cdf2dPath)
$srcOurs = [System.Drawing.Bitmap]::FromFile($oursPath)
$srcRef = [System.Drawing.Bitmap]::FromFile($refPath)
$crops = @(
    @{ Img = $srcRandom; Name = "Random"; Key = "Random" },
    @{ Img = $srcCdf; Name = "2D CDF"; Key = "Cdf2D" },
    @{ Img = $srcOurs; Name = $OursDisplayName; Key = "Ours" },
    @{ Img = $srcRef; Name = "Reference"; Key = $null }
)

$closeupLabelH = if ($OverlayLabels) { 0 } elseif ($showTime) { 44 } else { 26 }
$closeupRowH = $UpscaleTo + $closeupLabelH
$numRows = [Math]::Max(1, $chosen.Count)
# v8: cellW now tracks UpscaleTo directly (+ a small gap) instead of a fixed W/4, so bumping
# UpscaleTo to make closeups bigger doesn't crowd/overlap adjacent cells - previously cellW
# was fixed at the SOURCE image's own W/4 (480 for a 1920-wide render) regardless of
# UpscaleTo, which only happened to roughly fit when UpscaleTo(500) was close to 480.
$cellGap = 16
$cellW = $UpscaleTo + $cellGap
$closeupCanvasW = $cellW * 4

$allCloseups = New-Object System.Drawing.Bitmap($closeupCanvasW, ($closeupRowH * $numRows))
$g2 = [System.Drawing.Graphics]::FromImage($allCloseups)
$g2.Clear([System.Drawing.Color]::White)
$g2.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::NearestNeighbor
$g2.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit

for ($r = 0; $r -lt $chosen.Count; $r++) {
    $region = $chosen[$r]
    $rowY = $r * $closeupRowH
    $markerColor = $markerColors[$r % $markerColors.Count]
    $srcRect = New-Object System.Drawing.Rectangle($region.X, $region.Y, $CropSize, $CropSize)

    for ($i = 0; $i -lt 4; $i++) {
        $cellX = $i * $cellW
        $destX = $cellX + [int](($cellW - $UpscaleTo) / 2)
        if ($destX -lt $cellX) { $destX = $cellX }
        $destRect = New-Object System.Drawing.Rectangle($destX, ($rowY + $closeupLabelH), $UpscaleTo, $UpscaleTo)
        $g2.DrawImage($crops[$i].Img, $destRect, $srcRect, [System.Drawing.GraphicsUnit]::Pixel)
        $borderPen = New-Object System.Drawing.Pen($markerColor, $DividerWidth)
        $g2.DrawRectangle($borderPen, $destRect)
        $nameRect2 = New-Object System.Drawing.RectangleF($cellX, ($rowY + 1), $cellW, 26)
        if ($OverlayLabels) { Draw-OutlinedString $g2 $crops[$i].Name $font $nameRect2 $sf }
        else { $g2.DrawString($crops[$i].Name, $font, $brush, $nameRect2, $sf) }
        if ($showTime -and $crops[$i].Key -and $Metrics.ContainsKey($crops[$i].Key)) {
            $ms = $Metrics[$crops[$i].Key].Ms
            $timeRect = New-Object System.Drawing.RectangleF($cellX, ($rowY + 27), $cellW, 20)
            $timeText = "Time: {0:N1}ms" -f $ms
            if ($OverlayLabels) { Draw-OutlinedString $g2 $timeText $metricFont $timeRect $sf }
            else { $g2.DrawString($timeText, $metricFont, $brush, $timeRect, $sf) }
        }
    }
}

# --- Save composite and closeups as two SEPARATE files if their widths differ (v8: bigger
# UpscaleTo makes closeupCanvasW wider than the source photo's W) - stacking mismatched
# widths into one file with a blank-gap-detection trick (the original approach) only works
# cleanly when both blocks are the same width; two files sidesteps that entirely and is more
# robust regardless of how big UpscaleTo gets. When they DO match (the common case), still
# write a single stacked file for backward compatibility with compositors expecting one.
if ($closeupCanvasW -eq $W) {
    $finalH = $compositeH + 10 + ($closeupRowH * $numRows)
    $final = New-Object System.Drawing.Bitmap($W, $finalH)
    $g3 = [System.Drawing.Graphics]::FromImage($final)
    $g3.Clear([System.Drawing.Color]::White)
    $g3.DrawImage($composite, 0, 0)
    $g3.DrawImage($allCloseups, 0, ($compositeH + 10))
    $final.Save($OutPath, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Host "Saved figure to $OutPath"
    $final.Dispose()
}
else {
    $composite.Save($OutPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $closeupsPath = $OutPath -replace '\.png$', '_closeups.png'
    $allCloseups.Save($closeupsPath, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Host "Saved full-frame figure to $OutPath"
    Write-Host "Saved closeups (separate file, different width) to $closeupsPath"
}

$srcRandom.Dispose(); $srcCdf.Dispose(); $srcOurs.Dispose(); $srcRef.Dispose()
$refImg.Bitmap.Dispose(); $randImg.Bitmap.Dispose(); $cdfImg.Bitmap.Dispose(); $oursImg.Bitmap.Dispose()
$splitBmp.Dispose(); $composite.Dispose(); $allCloseups.Dispose()
