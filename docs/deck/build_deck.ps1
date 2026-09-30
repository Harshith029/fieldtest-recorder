# Builds the SIH26231 idea deck on the OFFICIAL SIH 2026 template through PowerPoint itself.
# Usage: powershell -File build_deck.ps1 [-TeamId "..."] [-TeamName "..."]
param([string]$TeamId = "[Team ID]", [string]$TeamName = "[Team Name]")
$RepoUrl = "https://github.com/Harshith029/fieldtest-recorder"
$RepoText = "github.com/Harshith029/fieldtest-recorder"
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent (Split-Path -Parent $here)
$out = Join-Path $here "SIH26231_Idea_Submission.pptx"
Copy-Item (Join-Path $root "docs\sih2026\SIH2026_Idea_Presentation_Template.pptx") $out -Force

# ---------------------------------------------------------------- palette (SIH blue family + evidence colours)
function C([string]$hex) { $r = [Convert]::ToInt32($hex.Substring(0, 2), 16); $g = [Convert]::ToInt32($hex.Substring(2, 2), 16); $b = [Convert]::ToInt32($hex.Substring(4, 2), 16); return $r + 256 * $g + 65536 * $b }
$NAVY = "1F3864"; $BLUE = "0070C0"; $INK = "262626"; $MUTED = "595959"; $CARD = "EEF3FA"; $LINE = "B4C7E7"
$GREEN = "2E7D32"; $ORANGE = "C55A11"; $GREY = "7F7F7F"; $WHITE = "FFFFFF"
$FONT = "Arial"

function Style($range, [double]$size, [string]$color = $INK, [bool]$bold = $false, [bool]$italic = $false) {
    $range.Font.Name = $FONT; $range.Font.Size = $size; $range.Font.Color.RGB = (C $color)
    $range.Font.Bold = [int]$bold * -1; $range.Font.Italic = [int]$italic * -1
}

# paras: array of @{ runs = @(@{t; b; c; i}); size; bullet; align; after }
function Fill-Text($tf, $paras, [double]$defSize = 11) {
    try { $tf.WordWrap = -1; $tf.AutoSize = 0 } catch { }          # table cells refuse AutoSize changes
    $tf.MarginLeft = 0; $tf.MarginRight = 0; $tf.MarginTop = 0; $tf.MarginBottom = 0
    $tr = $tf.TextRange; $tr.Text = ""
    for ($i = 0; $i -lt $paras.Count; $i++) {
        $p = $paras[$i]; $size = if ($p.size) { $p.size } else { $defSize }
        foreach ($run in $p.runs) {
            $r = $tr.InsertAfter($run.t)
            $col = if ($run.c) { $run.c } else { $INK }
            Style $r $size $col ([bool]$run.b) ([bool]$run.i)
        }
        if ($i -lt $paras.Count - 1) { $null = $tr.InsertAfter("`r") }
    }
    for ($i = 0; $i -lt $paras.Count; $i++) {
        $p = $paras[$i]; $pf = $tr.Paragraphs($i + 1).ParagraphFormat
        $pf.Alignment = if ($p.align) { $p.align } else { 1 }
        $pf.LineRuleAfter = 0; $pf.LineRuleBefore = 0                  # spacing in points, not lines
        $pf.SpaceAfter = if ($null -ne $p.after) { $p.after } else { 3 }
        $pf.SpaceBefore = 0
        $pf.LineRuleWithin = -1; $pf.SpaceWithin = 1.0
        if ($p.bullet) {
            $pf.Bullet.Visible = -1; $pf.Bullet.Character = 8226; $pf.Bullet.Font.Color.RGB = (C $BLUE)
            $tr.Paragraphs($i + 1).IndentLevel = 1
        } else { $pf.Bullet.Visible = 0 }
    }
    if (@($paras | Where-Object { $_.bullet }).Length -gt 0) { $lv = $tf.Ruler.Levels.Item(1); $lv.FirstMargin = 0; $lv.LeftMargin = 10 }
}

function T([string]$t, [bool]$b = $false, [string]$c = $null, [bool]$i = $false) { return @{ t = $t; b = $b; c = $c; i = $i } }
function P($runs, [double]$size = 0, [bool]$bullet = $false, [int]$align = 1, $after = $null) {
    $h = @{ runs = @($runs); bullet = $bullet; align = $align; after = $after }; if ($size -gt 0) { $h.size = $size }; return $h
}

function Add-Text($slide, $l, $t, $w, $h, $paras, [double]$defSize = 11, [int]$anchor = 1) {
    $sh = $slide.Shapes.AddTextbox(1, $l, $t, $w, $h)
    Fill-Text $sh.TextFrame $paras $defSize
    $sh.TextFrame.VerticalAnchor = $anchor
    return $sh
}

function Add-Box($slide, [int]$type, $l, $t, $w, $h, [string]$fill, [string]$line = $null) {
    $sh = $slide.Shapes.AddShape($type, $l, $t, $w, $h)
    $sh.Fill.Solid(); $sh.Fill.ForeColor.RGB = (C $fill)
    if ($line) { $sh.Line.Visible = -1; $sh.Line.ForeColor.RGB = (C $line); $sh.Line.Weight = 0.75 } else { $sh.Line.Visible = 0 }
    $sh.Shadow.Visible = 0
    if ($type -eq 5) { $sh.Adjustments.Item(1) = 0.12 }
    return $sh
}

function Add-Pill($slide, $l, $t, [string]$kind) {
    $map = @{ code = @($GREEN, "PROVEN IN CODE", 62); sim = @($ORANGE, "SIMULATED", 48); next = @($GREY, "NEXT", 28); law = @($NAVY, "PRIMARY SOURCE", 64) }
    $k = $map[$kind]
    $sh = Add-Box $slide 5 $l $t $k[2] 11 $k[0]
    $sh.Adjustments.Item(1) = 0.5
    Fill-Text $sh.TextFrame @((P (T $k[1] $true $WHITE) 6.5 $false 2 0))
    $sh.TextFrame.VerticalAnchor = 3
    return $sh
}

function Add-Arrow($slide, $x1, $y1, $x2, $y2, [string]$color = $BLUE) {
    $ln = $slide.Shapes.AddLine($x1, $y1, $x2, $y2)
    $ln.Line.ForeColor.RGB = (C $color); $ln.Line.Weight = 1.5; $ln.Line.EndArrowheadStyle = 2
    return $ln
}

function Set-Chrome($slide, [string]$title, [double]$titleSize = 32) {
    foreach ($sh in @($slide.Shapes)) {
        if ($sh.Name -like "Oval*") {
            $sh.TextFrame.TextRange.Text = $TeamName
            $sh.TextFrame.TextRange.Font.Size = if ($TeamName.Length -gt 14) { 11 } else { 14 }
            $sh.TextFrame.TextRange.Font.Bold = -1
        }
        if ($sh.Name -eq "Title 1") {
            $sh.Left = 140; $sh.Width = 625; $sh.Top = 8; $sh.Height = 62
            $sh.TextFrame.TextRange.Text = $title
            $sh.TextFrame.TextRange.Font.Size = $titleSize
        }
    }
    foreach ($sh in @($slide.Shapes)) { if ($sh.Name -eq "TextBox 8") { $sh.Delete() } }
}

$app = New-Object -ComObject PowerPoint.Application
try {
    $pres = $app.Presentations.Open($out, 0, 0, 0)
    $pres.Slides.Item(7).Delete()                                        # instructions slide (limit: 6 incl. title)

    # ================================================================ 1. TITLE
    $s = $pres.Slides.Item(1)
    $sub = $s.Shapes.Item("Subtitle 3").TextFrame.TextRange
    $sub.Paragraphs(2).Text = "FieldTest Recorder"
    $tb = $s.Shapes.Item("TextBox 9")
    $vals = @(
        @("Problem Statement ID – ", "SIH26231"),
        @("Problem Statement Title – ", "Digital Companion for Field Drug Testing"),
        @("Theme – ", "MedTech / BioTech / HealthTech"),
        @("PS Category – ", "Software"),
        @("Team ID – ", $TeamId),
        @("Team Name – ", $TeamName))
    $tr = $tb.TextFrame.TextRange
    for ($i = 0; $i -lt 6; $i++) {
        $para = $tr.Paragraphs($i + 2)
        $body = $para.Text.TrimEnd("`r")                                 # replace the words, keep the paragraph mark
        $para.Characters(1, $body.Length).Text = $vals[$i][0] + $vals[$i][1]
        $para = $tr.Paragraphs($i + 2)
        $para.Font.Size = 16; $para.Font.Bold = -1
        $pf = $para.ParagraphFormat; $pf.Alignment = 1
        $pf.LineRuleWithin = -1; $pf.SpaceWithin = 1.0; $pf.LineRuleAfter = 0; $pf.SpaceAfter = 16; $pf.LineRuleBefore = 0; $pf.SpaceBefore = 0
        $para.Characters($vals[$i][0].Length + 1, $vals[$i][1].Length).Font.Bold = 0
        $para.Characters($vals[$i][0].Length + 1, $vals[$i][1].Length).Font.Color.RGB = (C $NAVY)
    }
    $tb.Width = 440

    # ================================================================ 2. IDEA
    $s = $pres.Slides.Item(2)
    Set-Chrome $s "FieldTest Recorder" 34
    $null = Add-Text $s 140 64 625 20 @((P (T "A guided, measured and signed field test for NCB's Narcotic Drugs Detection Kit" $false $NAVY $true) 13 $false 2 0))

    # column A: the gap
    $null = Add-Box $s 5 22 96 262 396 $CARD
    $null = Add-Text $s 34 106 240 18 @((P (T "THE GAP TODAY" $true $NAVY) 12))
    $null = Add-Text $s 34 130 240 356 @(
        (P @((T "Read by eye. " $true), (T "Officers match the kit's colour against a printed chart; nothing proves a test happened at a place and time (NCB, this problem statement).")) 11 $true 1 12),
        (P @((T "No standard. " $true), (T "Bombay HC (2021): NCB ""has not prescribed the standards""; field testing is ""arbitrary"", and a bare mention in the panchnama is not enough.")) 11 $true 1 12),
        (P @((T "Wrong drug, wrong quantity. " $true), (T "Kerala HC (2024, Anuraj): seized ""MDMA"" was methamphetamine, which changes the NDPS quantity category.")) 11 $true 1 12),
        (P @((T "So: " $true), (T "disputed seizures, bail on procedure, and no data on how often field tests are wrong.")) 11 $true 1 0)) 11

    # column B: the solution as a 6-step flow
    $null = Add-Text $s 300 100 330 18 @((P (T "HOW IT WORKS (OFFLINE, ON THE OFFICER'S PHONE)" $true $NAVY) 12))
    $steps = @(
        @("Guide", "NCB kit Tests A–E in the printed flow-chart order: drops, wait time, which layer to read"),
        @("Capture", "Photo of the reaction on a reference colour card, next to a reagent-only blank well"),
        @("Read", "Colour bands from the kit's own ranges: positive / no colour change / inconclusive + every drug it fits"),
        @("Sign", "Time, GPS, officer and image hash, signed in phone hardware and hash-chained"),
        @("Anchor", "A 14-character code written into the witness-signed panchnama"),
        @("Report", "Field Test Memo, Form-1 item 5, BSA s.63 data; anyone can verify offline"))
    for ($i = 0; $i -lt 6; $i++) {
        $y = 124 + $i * 61
        $c = Add-Box $s 9 300 $y 26 26 $BLUE
        Fill-Text $c.TextFrame @((P (T "$($i + 1)" $true $WHITE) 12 $false 2 0)); $c.TextFrame.VerticalAnchor = 3
        $null = Add-Text $s 334 ($y - 1) 296 56 @((P (T $steps[$i][0] $true $NAVY) 11.5 $false 1 1), (P (T $steps[$i][1]) 10 $false 1 0))
        if ($i -lt 5) { $null = Add-Arrow $s 313 ($y + 28) 313 ($y + 59) $LINE }
    }

    # column C: what is new
    $null = Add-Text $s 648 100 290 18 @((P (T "WHAT IS NEW" $true $NAVY) 12))
    $news = @(
        @("Says only what the chemistry supports", "Test E blue = ""cocaine or methaqualone"" until E3/E4 narrows it; warns when the NDPS quantity category can't be told in the field.", ""),
        @("Holds up when the sample amount varies", "Bands + blank well: 0% false positives where single-point colour matching gave up to 11.7%.", "sim"),
        @("Proves completeness, not just integrity", "Deleted or re-run tests are caught; not even our server admin can forge a record.", "code"),
        @("No new hardware", "Existing NCB kit + officer's phone + a printed card. Works offline; embeds in e-Sakshya as an SDK.", ""))
    for ($i = 0; $i -lt 4; $i++) {
        $y = 124 + $i * 92
        $null = Add-Box $s 5 648 $y 290 84 $CARD
        $null = Add-Text $s 658 ($y + 8) 272 72 @((P (T $news[$i][0] $true $NAVY) 11 $false 1 4), (P (T $news[$i][1]) 10.5 $false 1 0))
        if ($news[$i][2]) { $null = Add-Pill $s (930 - $(if ($news[$i][2] -eq "code") { 62 } else { 48 })) ($y + 5) $news[$i][2] }
    }

    # ================================================================ 3. TECHNICAL APPROACH
    $s = $pres.Slides.Item(3)
    Set-Chrome $s "TECHNICAL APPROACH" 32
    # phone box
    $null = Add-Box $s 5 22 96 280 268 $CARD $LINE
    $null = Add-Text $s 34 104 256 18 @((P (T "OFFICER'S PHONE (offline SDK)" $true $NAVY) 11))
    $chips = @(
        @("Guided NDDK protocol", "signed: steps, drops, read times, flow charts"),
        @("Capture", "CameraX / Camera2 RAW, card located by ArUco markers"),
        @("Colour engine", "card correction, blank well, CIELAB colour bands"),
        @("Record core", "ECDSA P-256 in StrongBox/TEE, SHA-256 chain"),
        @("Log + reports", "searchable log, Field Test Memo, Form-1 item 5"))
    for ($i = 0; $i -lt 5; $i++) {
        $y = 128 + $i * 46
        $null = Add-Box $s 5 34 $y 256 40 $WHITE $LINE
        $null = Add-Text $s 42 ($y + 5) 242 32 @((P (T $chips[$i][0] $true $INK) 10.5 $false 1 0), (P (T $chips[$i][1] $false $MUTED) 9 $false 1 0))
    }
    # server box
    $null = Add-Box $s 5 344 96 256 268 $CARD $LINE
    $null = Add-Text $s 356 104 236 18 @((P (T "THIN SERVER: NIC / MeitY cloud" $true $NAVY) 11))
    $srv = @(
        @("Enrolment", "Android key attestation + supervisor's DSC"),
        @("Sync", "idempotent, fork/replay checks, signed receipts"),
        @("Storage", "PostgreSQL + S3 write-once, durable checkpoints"),
        @("Search + lab loop", "case search; Rule 14 lab result vs field result"),
        @("Never trusted", "records verify without the server"))
    for ($i = 0; $i -lt 5; $i++) {
        $y = 128 + $i * 46
        $null = Add-Box $s 5 356 $y 232 40 $WHITE $LINE
        $null = Add-Text $s 364 ($y + 5) 218 32 @((P (T $srv[$i][0] $true $INK) 10.5 $false 1 0), (P (T $srv[$i][1] $false $MUTED) 9 $false 1 0))
    }
    $null = Add-Arrow $s 304 230 342 230 $BLUE
    $null = Add-Text $s 298 204 50 22 @((P (T "sync when online" $false $MUTED $true) 7.5 $false 2 0))
    # trust strip
    $null = Add-Box $s 5 22 374 578 56 $WHITE $LINE
    $null = Add-Text $s 34 381 490 44 @(
        (P @((T "Trust without trusting us: " $true $NAVY), (T "NCB signs the supervisor list; a supervisor's DSC binds officer + phone + key; the phone signs and chains every test; the chain heads of every phone go into the witness-signed panchnama. An offline verifier (same record core) checks it all in court.")) 9.5))
    $null = Add-Pill $s 532 381 "code"
    # tech chips row
    $null = Add-Text $s 22 440 578 50 @(
        (P @((T "Stack: " $true $NAVY), (T "Kotlin · CameraX/Camera2 · OpenCV · Android Keystore + key attestation · SQLCipher · RFC 8785 JSON · ECDSA P-256 · Spring Boot · PostgreSQL · S3 object lock · Parichay / Class 3 DSC")) 9.5 $false 1 3),
        (P @((T "Deliberately not used: " $true $NAVY), (T "blockchain, cloud AI, a neural-network ""drug detector"" (a colour test cannot identify a drug; the court must be able to re-run the reading)")) 9.5))
    # card image + status
    $img = Join-Path $root "ftr-reference\docs\validation\card\ftr-card-150x105mm.png"
    $pic = $s.Shapes.AddPicture($img, 0, -1, 620, 98, 316, 221)
    $pic.Line.Visible = -1; $pic.Line.ForeColor.RGB = (C $LINE); $pic.Line.Weight = 0.75
    $null = Add-Text $s 620 322 316 26 @((P (T "Reference card v2 (printable, 150 x 105 mm): 24 colour patches, 4 markers, SAMPLE and BLANK zones. The engine finds it in the print file." $false $MUTED $true) 8.5))
    $null = Add-Text $s 620 356 316 16 @((P (T "BUILT SO FAR" $true $NAVY) 11))
    $built = @(
        @("Reference implementation + one-command demo, 47 tests: github.com/Harshith029/fieldtest-recorder", "code"),
        @("17 experiments with 95% intervals (colour, liveness, night light, amount)", "sim"),
        @("Android app (Kotlin) on the same test vectors", "next"))
    for ($i = 0; $i -lt 3; $i++) {
        $y = 376 + $i * 38
        $null = Add-Pill $s 620 ($y + 2) $built[$i][1]
        $null = Add-Text $s 688 $y 248 36 @((P (T $built[$i][0]) 9.5))
    }

    # ================================================================ 4. FEASIBILITY AND VIABILITY
    $s = $pres.Slides.Item(4)
    Set-Chrome $s "FEASIBILITY AND VIABILITY" 30
    $stats = @(
        @("18/18", "tampering attacks caught, incl. insider-admin forgery and deleted records", "code"),
        @("15/15", "sync and failure scenarios handled, incl. restore from an old backup", "code"),
        @("11.7% → 0%", "false positives when the sample amount varies (single-point rule vs colour bands)", "sim"),
        @("89%", "NCB-kit chart outcomes read correctly, 1.7% wrong, rest inconclusive", "sim"))
    for ($i = 0; $i -lt 4; $i++) {
        $x = 22 + $i * 230
        $null = Add-Box $s 5 $x 96 220 96 $CARD
        $null = Add-Text $s ($x + 10) 102 200 36 @((P (T $stats[$i][0] $true $BLUE) 26 $false 1 0))
        $null = Add-Text $s ($x + 10) 140 200 36 @((P (T $stats[$i][1]) 9.5))
        $null = Add-Pill $s ($x + 210 - $(if ($stats[$i][2] -eq "code") { 62 } else { 48 })) 102 $stats[$i][2]
    }
    # risk table
    $null = Add-Text $s 22 204 600 16 @((P (T "CHALLENGES AND HOW WE HANDLE THEM" $true $NAVY) 11))
    $rows = @(
        @("Real reaction colours differ from the printed chart", "Validation by NCB/CFSL chemists under their licences: 1,296 captures at 3 sample amounts; we never handle narcotics"),
        @("Phones and light vary; glare; night raids", "Reference card + RAW capture; bad-light gate; flash/no-flash night mode; say ""inconclusive"" rather than guess"),
        @("Staged or swapped sample", "Capture starts before the reagent drop; liveness check; package label in frame; link to the s.105 video"),
        @("Rooted phone, insider, deleted records", "Hardware keys + attestation; supervisor-signed binding; panchnama anchor; server never trusted"),
        @("Access to SIMS / e-Sakshya not confirmed", "File exports first; the engine ships as an SDK e-Sakshya can embed"))
    $tbl = $s.Shapes.AddTable(6, 2, 22, 222, 600, 260)
    $tb = $tbl.Table
    $tb.ApplyStyle("{2D5ABB26-0587-4C30-8999-92F81FD0307C}")
    $tb.Columns.Item(1).Width = 200; $tb.Columns.Item(2).Width = 400
    $hdr = @("Challenge / risk", "Strategy")
    for ($c = 1; $c -le 2; $c++) {
        $cell = $tb.Cell(1, $c).Shape
        $cell.Fill.Visible = -1; $cell.Fill.Solid(); $cell.Fill.ForeColor.RGB = (C $NAVY)
        Fill-Text $cell.TextFrame @((P (T $hdr[$c - 1] $true $WHITE) 9.5 $false 1 0))
    }
    for ($r = 0; $r -lt 5; $r++) {
        for ($c = 1; $c -le 2; $c++) {
            $cell = $tb.Cell($r + 2, $c).Shape
            $cell.Fill.Visible = -1; $cell.Fill.Solid(); $cell.Fill.ForeColor.RGB = (C $(if ($r % 2 -eq 0) { $WHITE } else { $CARD }))
            Fill-Text $cell.TextFrame @((P (T $rows[$r][$c - 1] ($c -eq 1)) 10 $false 1 0))
        }
    }
    for ($r = 1; $r -le 6; $r++) { for ($c = 1; $c -le 2; $c++) { $tf = $tb.Cell($r, $c).Shape.TextFrame; $tf.MarginLeft = 6; $tf.MarginRight = 6; $tf.MarginTop = 6; $tf.MarginBottom = 6 } }
    for ($r = 1; $r -le 6; $r++) { $tb.Rows.Item($r).Height = 20 }
    # viability card
    $null = Add-Box $s 5 638 204 300 286 $CARD
    $null = Add-Text $s 650 212 278 16 @((P (T "WHY IT IS VIABLE" $true $NAVY) 11))
    $null = Add-Text $s 650 234 278 250 @(
        (P @((T "Existing kit, existing phones: " $true), (T "NCB already supplies the kit free; the only addition is a printed colour card per kit.")) 10.5 $true 1 9),
        (P @((T "Small infrastructure: " $true), (T "one app server pair, PostgreSQL, 1–3 TB a year of storage on NIC or MeitY-empanelled cloud.")) 10.5 $true 1 9),
        (P @((T "Government-owned: " $true), (T "NCB holds the signing keys, the colour standard and the code; open formats, no licences.")) 10.5 $true 1 9),
        (P @((T "Pass criteria set in advance: " $true), (T "false positives at most 1%, proven at 95% confidence (at least 299 negative controls); ""inconclusive"" at most 15%.")) 10.5 $true 1 9),
        (P @((T "Clear status: " $true), (T "every number here is labelled proven in code or simulated. Real-phone and real-kit numbers come next.")) 10.5 $true 1 0)) 10.5

    # ================================================================ 5. IMPACT AND BENEFITS
    $s = $pres.Slides.Item(5)
    Set-Chrome $s "IMPACT AND BENEFITS" 32
    $null = Add-Text $s 22 98 420 16 @((P (T "WHO BENEFITS" $true $NAVY) 11))
    $who = @(
        @("SO", "Seizing officer", "A guided test, a Field Test Memo and Form-1 item 5 filled in, and a record that shows good-faith action."),
        @("IO", "Investigating officer, prosecutor", "Checkable evidence for remand and bail; a Rule 10(2) grouping check before sampling; the lab result linked back."),
        @("CT", "Courts, defence, the accused", "Any expert can re-check the record offline; the quantity category is flagged as uncertain until the lab confirms."),
        @("HQ", "NCB headquarters and labs", "India's first field-vs-lab accuracy data, per kit batch and per test."))
    for ($i = 0; $i -lt 4; $i++) {
        $y = 120 + $i * 64
        $c = Add-Box $s 9 22 $y 36 36 $BLUE
        Fill-Text $c.TextFrame @((P (T $who[$i][0] $true $WHITE) 10.5 $false 2 0)); $c.TextFrame.VerticalAnchor = 3
        $null = Add-Text $s 68 ($y - 2) 372 60 @((P (T $who[$i][1] $true $NAVY) 11 $false 1 1), (P (T $who[$i][2]) 9.5 $false 1 0))
    }
    # before / after table
    $null = Add-Text $s 460 98 478 16 @((P (T "WHAT CHANGES FOR ONE SEIZURE" $true $NAVY) 11))
    $ba = @(
        @("Colour judged by eye", "Measured against a signed colour standard"),
        @("""Dark brown"" written in the panchnama", "Photo + reading + every drug the colour is consistent with"),
        @("No proof of time or place", "Signed time, GNSS time, GPS and officer"),
        @("Records can be rewritten later", "Deletions and re-runs are detectable"),
        @("Quantity category guessed", "Flagged when it can't be told in the field"),
        @("No kit accuracy data", "Field result vs lab result, per kit batch"))
    $tbl = $s.Shapes.AddTable(7, 2, 460, 118, 478, 260)
    $tb = $tbl.Table
    $tb.ApplyStyle("{2D5ABB26-0587-4C30-8999-92F81FD0307C}")
    $tb.Columns.Item(1).Width = 210; $tb.Columns.Item(2).Width = 268
    $h2 = @("Today (paper)", "With FieldTest Recorder")
    for ($c = 1; $c -le 2; $c++) {
        $cell = $tb.Cell(1, $c).Shape
        $cell.Fill.Visible = -1; $cell.Fill.Solid(); $cell.Fill.ForeColor.RGB = (C $(if ($c -eq 1) { $GREY } else { $NAVY }))
        Fill-Text $cell.TextFrame @((P (T $h2[$c - 1] $true $WHITE) 9.5 $false 1 0))
    }
    for ($r = 0; $r -lt 6; $r++) {
        for ($c = 1; $c -le 2; $c++) {
            $cell = $tb.Cell($r + 2, $c).Shape
            $cell.Fill.Visible = -1; $cell.Fill.Solid(); $cell.Fill.ForeColor.RGB = (C $(if ($r % 2 -eq 0) { $WHITE } else { $CARD }))
            Fill-Text $cell.TextFrame @((P (T $ba[$r][$c - 1] ($c -eq 2) $(if ($c -eq 1) { $MUTED } else { $INK })) 9.5 $false 1 0))
        }
    }
    for ($r = 1; $r -le 7; $r++) { for ($c = 1; $c -le 2; $c++) { $tf = $tb.Cell($r, $c).Shape.TextFrame; $tf.MarginLeft = 5; $tf.MarginRight = 5; $tf.MarginTop = 3; $tf.MarginBottom = 3 } }
    for ($r = 1; $r -le 7; $r++) { $tb.Rows.Item($r).Height = 20 }
    # real-case callout under the table
    $null = Add-Box $s 5 460 284 478 84 $WHITE $LINE
    $null = Add-Text $s 472 292 454 70 @(
        (P (T "Why a field report must not overstate: a real case" $true $NAVY) 11 $false 1 4),
        (P @((T "Anuraj v. State of Kerala (2024): " $true), (T "police alleged commercial-quantity MDMA; the lab found methamphetamine in intermediate quantity (MDMA 0.5 g / 10 g vs methamphetamine 2 g / 50 g). Our record states only what the kit's colour supports, lists every drug that colour fits, and warns when they fall under different NDPS thresholds.")) 9.5 $false 1 0))
    # benefits strip
    $null = Add-Box $s 5 22 380 916 108 $CARD
    $ben = @(
        @("Social", "Fairer remand and bail decisions; fewer cases lost on procedure; honest officers protected."),
        @("Economic", "No new hardware; reuses the free NCB kit and officers' phones; small hosting cost."),
        @("Environmental", "Paperless records; no extra consumables beyond one printed card per kit."),
        @("Scale", "1,15,236 NDPS cases in 2022 (MHA); every package in every case gets a field test."))
    for ($i = 0; $i -lt 4; $i++) {
        $x = 34 + $i * 228
        $null = Add-Text $s $x 394 214 92 @((P (T $ben[$i][0] $true $NAVY) 12 $false 1 5), (P (T $ben[$i][1]) 10.5 $false 1 0))
    }

    # ================================================================ 6. RESEARCH AND REFERENCES
    $s = $pres.Slides.Item(6)
    Set-Chrome $s "RESEARCH AND REFERENCES" 30
    $refsL = @(
        @("SIH26231 problem statement", "Narcotics Control Bureau, MHA; sih.gov.in"),
        @("NCB Narcotic Drugs Detection Kit", "NICFS, A Forensic Guide for Crime Investigators, ch. 8, Figs 8.12–8.16 (Tests A–E, flow charts)"),
        @("NDPS (Seizure, Storage, Sampling and Disposal) Rules 2022", "GSR 899(E): Rules 3, 5, 10(2), 13, 14"),
        @("Sagar Parshuram Joshi v. State of Maharashtra", "Bombay HC, 15 Jan 2021 (indiankanoon.org/doc/90970274)"),
        @("Masibur Khan v. State", "Delhi HC, 31 May 2023 (indiankanoon.org/doc/91398841)"),
        @("Anuraj v. State of Kerala", "Kerala HC, 2024: alleged MDMA found to be methamphetamine"))
    $refsR = @(
        @("NDPS small and commercial quantities", "S.O. 1055(E), 19 Oct 2001"),
        @("NCB Drug Law Enforcement Field Officers' Handbook", "narcoticsindia.nic.in"),
        @("BPR&D SOP: audio-video recording under BNSS; BSA 2023 s.63", "hash value in the electronic-record certificate"),
        @("NIJ Standard-0604.01", "Color Test Reagents/Kits for Preliminary Identification of Drugs of Abuse (US DoJ)"),
        @("Android key attestation; RFC 8785 (JSON canonicalisation)", "developer.android.com; rfc-editor.org"),
        @("MHA Rajya Sabha USQ 1832 (11 Dec 2024)", "NDPS case statistics"))
    foreach ($col in @(@($refsL, 22, 1), @($refsR, 482, 7))) {
        $paras = @()
        $n = $col[2]
        foreach ($r in $col[0]) { $paras += (P @((T "[$n] " $true $BLUE), (T $r[0] $true), (T " — $($r[1])" $false $MUTED)) 10.5 $false 1 9); $n++ }
        $null = Add-Text $s $col[1] 100 446 220 $paras 10.5
    }
    $null = Add-Box $s 5 22 322 916 166 $CARD
    $hdr6 = Add-Text $s 34 332 892 16 @((P @((T "OUR CODE AND RESEARCH: " $true $NAVY), (T $RepoText $true $BLUE)) 12))
    $lnk = $hdr6.TextFrame.TextRange.Find($RepoText)
    if ($lnk) { $lnk.ActionSettings.Item(1).Hyperlink.Address = $RepoUrl }
    $null = Add-Text $s 34 354 892 130 @(
        (P @((T "Working reference implementation with a one-command demo and 47 automated tests: " $true), (T "record format and offline verifier, colour engine, NCB kit protocol, searchable log, sync server. The Android app must match its outputs byte for byte.")) 10.5 $true 1 7),
        (P @((T "17 experiments with 95% confidence intervals, " $true), (T "including 18 tampering attacks, 15 failure scenarios, sample-amount tests, night light and staged-sample detection.")) 10.5 $true 1 7),
        (P @((T "An external review, re-checked claim by claim: " $true), (T "every confirmed defect was fixed and re-tested before this submission.")) 10.5 $true 1 7),
        (P @((T "Safety and law: " $true), (T "our team never handles narcotics; colour tests use published colours, the kit chart and safe dyes. Real-kit validation is designed for NCB or CFSL chemists.")) 10.5 $true 1 0)) 10.5

    $pres.Save()
    $pres.SaveAs(($out -replace '\.pptx$', '.pdf'), 32)
    "saved: $out (+ PDF), slides: $($pres.Slides.Count)"
    $pres.Close()
} catch {
    "ERROR at line $($_.InvocationInfo.ScriptLineNumber): $($_.Exception.Message)`n  $($_.InvocationInfo.Line.Trim())"
    try { $pres.Close() } catch {}
} finally { $app.Quit(); [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null }
