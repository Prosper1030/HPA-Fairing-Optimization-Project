# macOS Setup Guide

本專案原本是在 Windows 上開發，但主程式邏輯已經整理成可跨平台執行。macOS 端最重要的是把 Python 虛擬環境與 OpenVSP Python API 接好。

## 1. 安裝前提

- Python 3.11
- OpenVSP for macOS（請先安裝到 `/Applications`，常見名稱為 `OpenVSP.app`）

OpenVSP 官方 Python API 文件特別提醒：**Python 版本必須和 OpenVSP 編譯時使用的版本相容**。如果官方發行版的 Python API 無法直接匯入，就需要改用對應版本的 OpenVSP 發行版，或自行編譯 OpenVSP Python wrapper。

## 2. 建立並啟動環境

在專案根目錄執行：

```bash
source activate_env.sh
```

這個腳本會自動做幾件事：

- 建立 `vsp_env/`（如果還不存在）
- 啟動 `vsp_env/bin/activate`
- 安裝 `requirements.txt` 中的 Python 套件
- 嘗試從 `/Applications` 或 `$HOME/Applications` 找出 `OpenVSP.app`
- 自動補上 `PYTHONPATH` 與必要的動態函式庫搜尋路徑

## 3. 如果 OpenVSP 沒有被自動找到

可以手動指定：

```bash
export OPENVSP_APP="/Applications/OpenVSP.app"
source activate_env.sh
```

如果你已經知道 OpenVSP Python API 的實際資料夾，也可以直接指定：

```bash
export OPENVSP_PYTHON_PATH="/path/to/openvsp/python"
source activate_env.sh
```

## 4. 驗證環境

```bash
python -c "import openvsp as vsp; print(vsp.__file__)"
python tests/analyze_existing_file.py
```

如果第一行成功印出 `openvsp` 模組位置，就代表 Python API 已經接上。

## 5. 常用指令

```bash
python scripts/run_ga.py --config config/ga_config.json
python tests/run_final_generator.py
python tests/plot_side_view_curves.py
```

## 6. 常見問題

### `ModuleNotFoundError: No module named 'openvsp'`

代表 OpenVSP Python API 仍未被目前 shell 找到。先確認：

- `OpenVSP.app` 是否真的安裝在 `/Applications` 或 `$HOME/Applications`
- 你是否有用 `source activate_env.sh`，而不是直接執行 `./activate_env.sh`
- `OPENVSP_APP` 或 `OPENVSP_PYTHON_PATH` 是否指向正確位置

### `ImportError` 或 `.dylib` 載入失敗

通常表示 Python wrapper 找到了，但其依賴的 OpenVSP 動態函式庫路徑還沒補齊。重新 `source activate_env.sh`，讓腳本重新設定 `DYLD_FALLBACK_LIBRARY_PATH`；如果仍失敗，請確認 OpenVSP.app 本身是否能正常開啟。
