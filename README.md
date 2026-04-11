# HPA Fairing Optimization Project

Project Name: HPA Fairing Optimization Project

**人力飛機整流罩 GA 優化系統**

成大航太 × 日本鳥人間大賽專用

---

## 專案簡介

本專案使用 **CST (Class Shape Transformation)** 參數化方法與 **OpenVSP** 空氣動力分析工具，配合 **遺傳演算法 (GA)** 自動優化人力飛機整流罩設計。

### 核心特色

- **20 個基因參數**：完整控制整流罩幾何
- **上下非對稱截面**：M/N 指數可分開設定
- **CST 曲線**：峰值歸一化確保精確尺寸
- **自動 GA 優化**：收斂曲線、最佳模型自動生成
- **硬約束檢查**：座艙空間、踏板寬度等

---

## 快速開始

### 0. 建立環境

macOS / Linux：

```bash
source activate_env.sh
```

Windows PowerShell：

```powershell
. .\activate_env.ps1
```

詳細的 macOS 安裝流程請見 `docs/MAC_SETUP.md`。

### 1. 運行 GA 優化

```bash
# 使用預設配置（50代，20族群）
python scripts/run_ga.py

# 自訂參數
python scripts/run_ga.py --gen 100 --pop 30

# 使用配置檔案
python scripts/run_ga.py --config config/ga_config.json
```

### 2. 測試單一設計

```bash
python tests/test_expanded_parameters.py
```

### 3. 查看結果

輸出位於 `output/hpa_run_YYYYMMDD_HHMMSS/`：

- `vsp_models/best_design.vsp3` - 最佳模型（用 VSP GUI 開啟）
- `logs/convergence.png` - 收斂曲線
- `logs/best_gene.json` - 最佳基因參數

---

## 基因參數定義（20 個）

| 類別         | 參數        | 範圍        | 說明                   |
| ------------ | ----------- | ----------- | ---------------------- |
| **幾何**     | L           | 1.8-3.0 m   | 整流罩總長             |
|              | W_max       | 0.48-0.65 m | 最大全寬               |
|              | H_top_max   | 0.85-1.15 m | 上半部高度             |
|              | H_bot_max   | 0.25-0.50 m | 下半部高度             |
| **CST 形狀** | N1          | 0.4-0.9     | Class function（共用） |
|              | N2_top      | 0.5-1.0     | 上曲線 Shape function  |
|              | N2_bot      | 0.5-1.0     | 下曲線 Shape function  |
| **位置**     | X_max_pos   | 0.2-0.5     | 最大寬度位置           |
|              | X_offset    | 0.5-1.0 m   | 收縮開始位置           |
| **超橢圓**   | M_top       | 2.0-4.0     | 上半部 M 指數          |
|              | N_top       | 2.0-4.0     | 上半部 N 指數          |
|              | M_bot       | 2.0-4.0     | 下半部 M 指數          |
|              | N_bot       | 2.0-4.0     | 下半部 N 指數          |
| **尾部**     | tail_rise   | 0.05-0.20 m | 機尾上升高度           |
|              | blend_start | 0.65-0.85   | 混合開始位置           |
|              | blend_power | 1.5-3.0     | 混合曲線冪次           |
| **CST 權重** | w0          | 0.15-0.35   | 前段斜率               |
|              | w1          | 0.25-0.45   | 最大值附近             |
|              | w2          | 0.20-0.40   | 後段平滑               |
|              | w3          | 0.05-0.20   | 尾部收斂               |

---

## 專案結構

```
Fairing Design/
├── config/                   # 配置檔案
│   ├── fluid_conditions.json # 流體條件
│   └── ga_config.json        # GA 優化配置
├── src/                      # 核心模組
│   ├── optimization/         # 優化器
│   │   └── hpa_asymmetric_optimizer.py  # 主優化器
│   ├── analysis/             # 阻力分析
│   └── math/                 # 數學工具
├── scripts/                  # 可執行腳本
│   └── run_ga.py             # GA 運行腳本
├── tests/                    # 測試代碼
├── output/                   # 輸出結果
├── docs/                     # 文檔（含 macOS 安裝說明）
├── requirements.txt          # Python 依賴
├── activate_env.sh           # macOS/Linux 環境啟動腳本
└── archive/                  # 舊代碼備份
```

---

## 配置說明

### 流體條件 (`config/fluid_conditions.json`)

```json
{
  "flow_conditions": {
    "velocity": { "value": 6.5, "unit": "m/s" },
    "density": { "value": 1.225, "unit": "kg/m^3" },
    "viscosity": { "value": 1.7894e-5, "unit": "kg/(m*s)" }
  }
}
```

### GA 配置 (`config/ga_config.json`)

```json
{
  "ga_settings": {
    "population_size": 20,
    "n_generations": 50,
    "crossover_probability": 0.9,
    "seed": 42
  }
}
```

---

## 硬約束條件

| 約束     | 值     | 說明                |
| -------- | ------ | ------------------- |
| 車架包覆 | 0.3 m  | X_offset >= 0.3     |
| 踏板寬度 | 0.45 m | 踏板處全寬 >= 0.45  |
| 肩膀寬度 | 0.52 m | 肩膀處全寬 >= 0.52  |
| 肩膀上高 | 0.75 m | 肩膀處上高 >= 0.75  |
| 肩膀下高 | 0.25 m | 肩膀處下高 >= 0.25  |
| 機尾長度 | 1.5 m  | L - X_offset >= 1.5 |

---

## 環境需求

- **Python**: 3.11.0（虛擬環境 `vsp_env/`）
- **OpenVSP**: 3.42.3
- **requirements.txt**: `numpy`, `scipy`, `pymoo`, `matplotlib`

### 安裝依賴

```bash
python -m pip install -r requirements.txt
```

### OpenVSP 說明

- 專案內的 Python 程式都維持 `import openvsp as vsp`
- `openvsp` 不包含在 `requirements.txt` 內
- macOS 上請先安裝 OpenVSP.app，再用 `source activate_env.sh` 讓腳本自動補上 `PYTHONPATH`
- 若 OpenVSP 發行版的 Python wrapper 與你的 Python 版本不相容，需改用相容版本或自行編譯 OpenVSP Python API

---

## 開發指南

### 修改基因範圍

編輯 `src/optimization/hpa_asymmetric_optimizer.py` 中的 `GENE_BOUNDS`：

```python
GENE_BOUNDS = {
    'L': (1.8, 3.0),
    'W_max': (0.48, 0.65),
    # ...
}
```

### 添加新約束

編輯 `ConstraintChecker` 類中的 `check_all_constraints()` 方法。

### 修改適應度函數

編輯 `HPA_Optimizer.evaluate_individual()` 方法。

---

## Git 提交記錄

```
b0d26ab feat: 擴展基因參數從9個到20個
72e3958 feat: 建立GA架構和配置系統
```

---

## 授權與引用

**教育研究用途** - 成功大學航太工程學系

```
NCKU Aerospace - HPA Fairing Optimization Project (2026)
```

---

**最後更新**: 2026-01-07
**版本**: 4.0 (GA-Ready with 20 Parameters)
