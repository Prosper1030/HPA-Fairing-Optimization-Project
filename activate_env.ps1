# 強制使用虛擬環境的 Python
$env:PATH = "D:\Fairing Design\vsp_env\Scripts;" + $env:PATH
$env:VIRTUAL_ENV = "D:\Fairing Design\vsp_env"

# 設置別名
function python { & "D:\Fairing Design\vsp_env\Scripts\python.exe" $args }
function pip { & "D:\Fairing Design\vsp_env\Scripts\pip.exe" $args }

# 提示符
function prompt {
    "(vsp_env) PS $($executionContext.SessionState.Path.CurrentLocation)> "
}

Write-Host "✓ 虛擬環境已啟動 (vsp_env)" -ForegroundColor Green
Write-Host "Python: " -NoNewline
& "D:\Fairing Design\vsp_env\Scripts\python.exe" --version
