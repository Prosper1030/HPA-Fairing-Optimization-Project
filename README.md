# Birdman Fairing Optimization Project

🚁 **人力飛機整流罩空氣動力優化系統**

成大航太 × 日本鳥人間大賽專用

---

## 🎯 專案簡介

本專案使用 **CST (Class Shape Transformation)** 參數化方法與 **OpenVSP** 空氣動力分析工具，自動生成並優化人力飛機整流罩設計，目標是在滿足飛行員空間需求的前提下，找出低速飛行（6.5 m/s）阻力最小的設計。

### 核心特色
- ✅ **超橢圓截面**：比標準橢圓更好的空間利用率
- ✅ **CST 參數化**：極少參數控制流線型曲面
- ✅ **自動化流程**：從幾何生成到阻力分析一鍵完成
- ✅ **模組化架構**：易於擴充遺傳演算法等優化器
- ✅ **完整文檔**：API 指南、專案計劃、結構說明

---

## 🚀 快速開始

### 一鍵執行優化

**Windows Command Prompt:**
```cmd
optimize.bat
```

**PowerShell:**
```powershell
.\optimize.ps1
```

就這麼簡單！程式會自動生成多個設計並比較阻力。

### 快速測試單一設計

```cmd
run.bat scripts\test_single.py
```

### 查看輸出結果

所有結果檔案位於 `output/` 資料夾：
- `*.vsp3` - 用 OpenVSP GUI 開啟查看 3D 幾何
- `*_ParasiteBuildUp.csv` - 詳細阻力分解數據

---

## 📁 專案結構

```
Fairing Design/
├── src/                      # 核心模組（幾何、分析、優化）
├── scripts/                  # 可執行腳本
│   ├── main_optimization.py  # 主優化程式
│   └── test_single.py        # 快速測試
├── tests/                    # 測試代碼
│   └── experimental/         # 實驗性代碼區
├── output/                   # 輸出結果
├── docs/                     # 文檔
│   ├── OPENVSP_API_GUIDE.md      # API 使用指南
│   ├── PROJECT_MASTER_PLAN.md    # 專案總計劃
│   └── PROJECT_STRUCTURE.md      # 結構說明
├── optimize.bat/.ps1         # 快速啟動器 ⭐
└── run.bat/.ps1              # 通用腳本啟動器
```

詳細說明請見 [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)

---

## 🔧 環境需求

- **Python**: 3.11.0（虛擬環境已配置在 `vsp_env/`）
- **OpenVSP**: 3.42.3（需安裝在系統中）
- **作業系統**: Windows 10/11

> ⚠️ 注意：本專案使用預配置的虛擬環境，**無需手動安裝套件**。

---

## 📖 使用說明

### 1. 執行主優化程式

程式會批次處理多個設計案例（Type A, B, C），並輸出阻力排名。

**執行方式**：
```cmd
optimize.bat
```

**輸出範例**：
```
🏆 OPTIMIZATION RESULTS (Sorted by Drag)
==================================================
Rank   | Design           | Drag (N)   | Cd
--------------------------------------------------
1      | Type_C_Comfort   | 0.74477    | 0.000298
2      | Type_A_Standard  | 0.93324    | 0.000373
3      | Type_B_HighSpeed | 1.28823    | 0.000515

📊 Best Design: Type_C_Comfort
   → 42.2% improvement over worst
```

### 2. 添加新設計

編輯 `scripts/main_optimization.py` 中的 `design_queue`：

```python
{
    "name": "Type_D_Custom",
    "length": 2.7,              # 機身長度 (m)
    "n_nose": 0.5,              # 機頭形狀 (0.5=橢圓, 1.0=圓錐)
    "n_tail": 1.0,              # 機尾形狀
    "width_weights": [0.15, 0.20, 0.20, 0.05],  # CST 寬度控制點
    "height_weights": [0.20, 0.35, 0.25, 0.05], # CST 高度控制點
    "super_m": 2.5,             # 超橢圓寬度指數 (2.0=橢圓, >2.0=方形)
    "super_n": 2.5,             # 超橢圓高度指數
}
```

### 3. 參數說明

#### CST 形狀參數
- **N_nose / N_tail**: 控制頭尾形狀
  - 0.5: 橢圓形（圓潤）
  - 1.0: 圓錐形（尖銳）

- **weights**: 控制縱向分佈（4 個控制點）
  - 範圍：0.02 - 0.40
  - 影響座艙區域的隆起程度

#### 超橢圓指數
- **super_m / super_n**: 控制截面形狀
  - 2.0: 標準橢圓
  - 2.5: 稍微方形（**推薦**，容納肩膀）
  - 3.0: 更方形

---

## 🧪 開發與測試

### 創建實驗腳本

在 `tests/experimental/` 下創建新檔案：

```python
"""
實驗：測試超大 super_m 值的影響
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.geometry import CSTGeometryGenerator
from src.analysis import DragAnalyzer

# 你的實驗代碼
```

**執行**：
```cmd
run.bat tests\experimental\your_experiment.py
```

### 運行通用腳本

```cmd
run.bat <your_script.py>
```

`run.bat` 會自動使用虛擬環境的 Python。

---

## 🎓 學習資源

### 文檔
- **[OpenVSP API Guide](docs/OPENVSP_API_GUIDE.md)**: API 使用指南與常見錯誤
- **[Project Master Plan](docs/PROJECT_MASTER_PLAN.md)**: 專案總計劃與物理背景
- **[Project Structure](PROJECT_STRUCTURE.md)**: 檔案組織與命名規範

### 關鍵概念
- **CST 方法**: Kulfan, B. M. (2008) - Universal Parametric Geometry
- **超橢圓**: Superellipse - https://en.wikipedia.org/wiki/Superellipse
- **Component Buildup Method**: OpenVSP Parasite Drag 分析原理

---

## 📊 設計參考

### 已測試案例（6.5 m/s）

| 設計 | 長度 (m) | Super_M/N | 阻力 (N) | Cd | 特點 |
|------|----------|-----------|----------|-----|------|
| Type_C_Comfort | 2.2 | 2.8 | 0.745 | 0.000298 | 🏆 最低阻力 |
| Type_A_Standard | 2.5 | 2.5 | 0.933 | 0.000373 | 標準設計 |
| Type_B_HighSpeed | 3.0 | 2.3 | 1.288 | 0.000515 | 細長型（不推薦）|

**關鍵發現**：
- ⚠️ 細長型（High Fineness Ratio）因濕面積過大，阻力反而最高
- ✅ 短而粗的設計在低速下更有利
- ✅ 適度的超橢圓指數（2.5-2.8）可平衡空間與阻力

---

## 🔮 未來規劃

- [ ] **遺傳演算法優化器** (Priority 1)
  - 族群演化自動尋找最佳設計
  - 肩膀寬度約束（≥ 0.45m）

- [ ] **參數掃描工具**
  - 系統化探索設計空間
  - 生成熱圖與敏感度分析

- [ ] **結果可視化**
  - Pareto Front 繪圖
  - 幾何對比動畫

- [ ] **CFD 驗證**
  - 使用 SU2 或 OpenFOAM 驗證 Component Buildup 結果

---

## 🐛 疑難排解

### 執行時找不到模組
確認使用專案提供的啟動器：
```cmd
optimize.bat         # ✅ 正確
python main_optimization.py  # ❌ 錯誤（找不到虛擬環境）
```

### 分析後找不到 CSV
1. 檢查 `output/` 資料夾
2. 用 OpenVSP GUI 開啟 .vsp3 檢查幾何是否正常
3. 查看終端輸出的錯誤訊息

### 幾何顯示為線或點
截面設定錯誤，檢查 `src/geometry/cst_geometry.py` 中的 `ChangeXSecShape` 呼叫。

詳細除錯指南請見 [docs/OPENVSP_API_GUIDE.md](docs/OPENVSP_API_GUIDE.md)。

---

## 📜 授權與引用

**教育研究用途** - 成功大學航太工程學系

如需引用本專案，請註明：
```
NCKU Aerospace - Birdman HPA Fairing Optimization Project (2025)
```

---

## 👥 貢獻者

- **專案發起**: 成大航太人力飛機團隊
- **技術實作**: Claude Code (AI Assistant) × 航太系學生
- **目標賽事**: 日本鳥人間大賽 (Japan Birdman Rally)

---

**最後更新**: 2025-01-03
**版本**: 3.0 (CST-SuperEllipse Architecture)

Happy Flying! 🛩️
