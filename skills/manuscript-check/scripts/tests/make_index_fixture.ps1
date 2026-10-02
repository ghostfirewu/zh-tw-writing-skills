# Build tests\index_typeset.pdf: 2 unnumbered front-matter pages, then 6 body pages numbered 1-6
# with a running head and a footnote. Keep this file ASCII-only; Chinese text lives in index_fixture.json.
$ErrorActionPreference = 'Stop'
$cfg = Get-Content "$PSScriptRoot\index_fixture.json" -Raw -Encoding utf8 | ConvertFrom-Json
$w = New-Object -ComObject Word.Application
$w.DisplayAlerts = 0

function EndPos($doc) { $r = $doc.Paragraphs.Last.Range; $r.MoveEnd(1, -1) | Out-Null; $r.Collapse(0); return $r }

try {
    $d = $w.Documents.Add()
    $first = $true
    foreach ($t in $cfg.front) {
        if (-not $first) { (EndPos $d).InsertBreak(7) }      # page break
        $first = $false
        (EndPos $d).InsertAfter($t)
    }
    (EndPos $d).InsertBreak(2)                                # section break, next page
    $firstBody = $true
    foreach ($pg in $cfg.body) {
        if (-not $firstBody) { (EndPos $d).InsertBreak(7) }
        $firstBody = $false
        (EndPos $d).InsertAfter($pg.text)
        if ($pg.footnote) { $fn = $d.Footnotes.Add((EndPos $d)); $fn.Range.Text = $pg.footnote }
    }
    $s2 = $d.Sections(2)
    $s2.Headers(1).LinkToPrevious = $false
    $s2.Footers(1).LinkToPrevious = $false
    $s2.Headers(1).Range.Text = $cfg.header
    $s2.Footers(1).PageNumbers.RestartNumberingAtSection = $true
    $s2.Footers(1).PageNumbers.StartingNumber = 1
    $s2.Footers(1).PageNumbers.Add(1, $true) | Out-Null
    $pdf = "$PSScriptRoot\index_typeset.pdf"
    if (Test-Path $pdf) { Remove-Item $pdf }
    $d.ExportAsFixedFormat($pdf, 17)
    $d.Close(0)
} finally { $w.Quit() }
"built index_typeset.pdf"
