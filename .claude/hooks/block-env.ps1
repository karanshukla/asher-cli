$raw = [Console]::In.ReadToEnd()
try {
    $j = $raw | ConvertFrom-Json
    if ($j.file_path -match '\.env$') {
        Write-Output "Blocked: .env contains real credentials — edit it manually if needed"
        exit 2
    }
} catch {}
exit 0
