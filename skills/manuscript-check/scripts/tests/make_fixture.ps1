# Build tests\fixture.docx from tests\fixture.json with Word (needed only when the fixture changes).
# Keep this file ASCII-only; Chinese text lives in fixture.json.
param([string]$Out = "$PSScriptRoot\fixture.docx")
$ErrorActionPreference = 'Stop'
$items = Get-Content "$PSScriptRoot\fixture.json" -Raw -Encoding utf8 | ConvertFrom-Json
$styleMap = @{ 'h1' = -2; 'h2' = -3; 'p' = -1; 'cap' = -35 }
# Collapsed range just before the last paragraph mark
function EndPos($doc) { $r = $doc.Paragraphs.Last.Range; $r.MoveEnd(1, -1) | Out-Null; $r.Collapse(0); return $r }
$w = New-Object -ComObject Word.Application
$w.DisplayAlerts = 0
try {
    $d = $w.Documents.Add()
    $first = $true
    foreach ($it in $items) {
        if (-not $first) { $d.Content.InsertParagraphAfter() }
        $first = $false
        $p = $d.Paragraphs($d.Paragraphs.Count)
        $p.Style = [int]$styleMap[$it.style]
        $r = EndPos $d
        $r.InsertAfter($it.text)
        if ($it.del) {
            $r = EndPos $d
            $r.InsertAfter($it.del)
            $delStart = $r.Start
            $d.TrackRevisions = $true
            $d.Range($delStart, $delStart + $it.del.Length).Delete() | Out-Null
            $r = EndPos $d
            $r.InsertAfter($it.ins)
            $d.TrackRevisions = $false
        }
        if ($it.footnote) {
            $r = EndPos $d
            $fn = $d.Footnotes.Add($r)
            $fn.Range.Text = $it.footnote
        }
    }
    if (Test-Path $Out) { Remove-Item $Out }
    $d.SaveAs2($Out, 16)
    $d.Close(0)
} finally { $w.Quit() }
"saved $Out"
