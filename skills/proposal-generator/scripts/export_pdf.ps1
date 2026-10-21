# 用本机 Microsoft Word 更新目录页码并导出 PDF（Windows）。
# 用法：powershell -ExecutionPolicy Bypass -File export_pdf.ps1 "D:\path\方案A.docx" ["D:\path\方案B.docx" ...]
# 说明：
#  - 每份文档单独启动一次 Word：部分 Word 版本（如 2007）导出 PDF 后关闭文档会崩溃，复用同一进程会导致后续文件失败。
#  - 会先更新目录（TOC）页码并保存 docx，再另存为同名 PDF。
#  - 无 Word 时可改用 LibreOffice：soffice --headless --convert-to pdf <docx>（目录页码需先在 Word/WPS 中更新）。
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Files)

foreach ($f in $Files) {
    $src = (Resolve-Path $f).Path
    $pdf = [IO.Path]::ChangeExtension($src, ".pdf")
    Get-Process WINWORD -ErrorAction SilentlyContinue | Stop-Process -Force
    $w = New-Object -ComObject Word.Application
    $w.Visible = $false
    $w.DisplayAlerts = 0
    try {
        $doc = $w.Documents.Open($src)
        if ($doc.TablesOfContents.Count -gt 0) { $doc.TablesOfContents.Item(1).Update() }
        $doc.Save()
        $doc.SaveAs([ref]$pdf, [ref]17)
        Write-Output ("{0} -> {1} 页" -f (Split-Path $pdf -Leaf), $doc.ComputeStatistics(2))
        try { $doc.Close() } catch {}
    } catch {
        Write-Output "导出失败：$src  $_"
    } finally {
        try { $w.Quit() } catch {}
        Get-Process WINWORD -ErrorAction SilentlyContinue | Stop-Process -Force
    }
}
