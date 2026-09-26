param([Parameter(Mandatory=$true)][string]$DocumentPath,[Parameter(Mandatory=$true)][string]$PdfPath)
$taskDocPath = [IO.Path]::GetFullPath($DocumentPath)
$taskPdfPath = [IO.Path]::GetFullPath($PdfPath)
$taskApp = New-Object -ComObject Word.Application
$taskApp.Visible = $false
$taskApp.DisplayAlerts = 0
try {
    $taskDoc = $taskApp.Documents.Open($taskDocPath,$false,$false)
    $taskDoc.Repaginate()
    $null = $taskDoc.Fields.Update()
    foreach ($taskToc in $taskDoc.TablesOfContents) { $taskToc.Update() }
    foreach ($taskToc in $taskDoc.TablesOfContents) {
        $taskToc.Range.Font.NameFarEast = '宋体'
        $taskToc.Range.Font.Name = 'Times New Roman'
        $taskToc.Range.Font.Size = 12
        $taskToc.Range.Font.Bold = 0
        $taskToc.Range.Font.Color = 0
        foreach ($taskParagraph in $taskToc.Range.Paragraphs) {
            $taskStyleName = $taskParagraph.Range.Style.NameLocal
            if ($taskStyleName -match '(TOC|目录)\s*1$') {
                $taskParagraph.Range.Font.Bold = -1
                $taskParagraph.Format.KeepWithNext = -1
            } else {
                $taskParagraph.Format.KeepWithNext = 0
            }
        }
    }
    $taskDoc.Repaginate()
    foreach ($taskToc in $taskDoc.TablesOfContents) { $taskToc.UpdatePageNumbers() }
    foreach ($taskToc in $taskDoc.TablesOfContents) { $taskToc.Range.Paragraphs.Item(1).Range.Font.Bold = -1 }
    $taskDoc.Save()
    $taskDoc.ExportAsFixedFormat($taskPdfPath,17)
    $taskInfo = [PSCustomObject]@{Pages=$taskDoc.ComputeStatistics(2); TOCs=$taskDoc.TablesOfContents.Count; File=$taskDocPath}
    $taskInfo | ConvertTo-Json -Compress
    $taskDoc.Close(0)
} finally { $taskApp.Quit() }
