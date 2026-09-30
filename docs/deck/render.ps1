# Render a .pptx with PowerPoint: one PNG per slide (+ optional PDF). Usage: render.ps1 deck.pptx outprefix [-Pdf]
param([string]$Deck, [string]$Prefix, [switch]$Pdf)
$Deck = (Resolve-Path $Deck).Path
$app = New-Object -ComObject PowerPoint.Application
try {
    $pres = $app.Presentations.Open($Deck, -1, 0, 0)          # ReadOnly, Untitled=false, WithWindow=false
    $w = [int]($pres.PageSetup.SlideWidth * 2); $h = [int]($pres.PageSetup.SlideHeight * 2)
    $i = 0
    foreach ($s in $pres.Slides) { $i++; $s.Export("$Prefix-$i.png", "PNG", $w, $h) }
    if ($Pdf) { $pres.SaveAs(($Deck -replace '\.pptx$', '.pdf'), 32) }
    "slides: $i  size: $($pres.PageSetup.SlideWidth) x $($pres.PageSetup.SlideHeight) pt"
    $pres.Close()
} finally { $app.Quit(); [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null }
