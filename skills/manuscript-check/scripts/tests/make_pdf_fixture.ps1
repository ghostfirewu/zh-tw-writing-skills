# Build the collation fixture: tests\collate_src.docx (the final manuscript) and
# tests\collate_typeset.pdf (a "typeset" copy with planted differences, running head and page numbers).
# Keep this file ASCII-only; all Chinese text lives in collate_fixture.json.
$ErrorActionPreference = 'Stop'
$cfg = Get-Content "$PSScriptRoot\collate_fixture.json" -Raw -Encoding utf8 | ConvertFrom-Json
$w = New-Object -ComObject Word.Application
$w.DisplayAlerts = 0

function EndPos($doc) { $r = $doc.Paragraphs.Last.Range; $r.MoveEnd(1, -1) | Out-Null; $r.Collapse(0); return $r }

function Build($doc) {
    $first = $true
    foreach ($it in $cfg.paragraphs) {
        if (-not $first) { $doc.Content.InsertParagraphAfter() }
        $first = $false
        $doc.Paragraphs.Last.Style = [int]$it.style
        $text = $it.text
        if ($it.sentences) {
            $text = ''
            foreach ($n in $it.sentences) { $text += ($cfg.sentence -f $n) }
        }
        (EndPos $doc).InsertAfter($text)
        if ($it.footnote) {
            $fn = $doc.Footnotes.Add((EndPos $doc))
            $fn.Range.Text = $it.footnote
        }
    }
}

function ReplaceAll($doc, $a, $b) {
    foreach ($story in @($doc.Content, $doc.StoryRanges(2))) {
        if ($null -eq $story) { continue }
        $f = $story.Find
        $f.ClearFormatting(); $f.Replacement.ClearFormatting()
        $f.Execute($a, $true, $false, $false, $false, $false, $true, 0, $false, $b, 2) | Out-Null
    }
}

try {
    $d = $w.Documents.Add()
    Build $d
    $src = "$PSScriptRoot\collate_src.docx"
    if (Test-Path $src) { Remove-Item $src }
    $d.SaveAs2($src, 16)

    foreach ($e in $cfg.edits) { ReplaceAll $d $e.find $e.replace }
    # move the caption paragraph to after the given anchor text
    $cap = $d.Content; $cap.Find.Execute($cfg.move.caption) | Out-Null
    $capPara = $cap.Paragraphs(1).Range
    $capText = $capPara.Text
    $capPara.Delete() | Out-Null
    $anchor = $d.Content; $anchor.Find.Execute($cfg.move.after) | Out-Null
    $anchor.Paragraphs(1).Range.InsertParagraphAfter()
    $anchor.Paragraphs(1).Next().Range.InsertBefore($capText.TrimEnd("`r"))

    # typesetting: smaller page, running head, page numbers
    $ps = $d.PageSetup
    $ps.PageWidth = 420; $ps.PageHeight = 595; $ps.HeaderDistance = 22; $ps.FooterDistance = 22
    $d.Sections(1).Headers(1).Range.Text = $cfg.header
    $d.Sections(1).Footers(1).PageNumbers.Add(1, $true) | Out-Null
    $pdf = "$PSScriptRoot\collate_typeset.pdf"
    if (Test-Path $pdf) { Remove-Item $pdf }
    $d.ExportAsFixedFormat($pdf, 17)
    $d.Close(0)
} finally { $w.Quit() }
"built collate_src.docx and collate_typeset.pdf"
