# HPA 整流罩優化器 - 專案結構說明

**最後更新：2026-01-07**

---

## 📁 整理後的目錄結構

```
Fairing Design/
│

├── 📂 src/                              # 核心源代碼（模組化）
│   ├── 📂 analysis/                     # 分析模組
│   │   └── drag_analysis.py             # ✅ DragAnalyzer 阻力計算（已修復）
│   │
│   ├── 📂 geometry/                     # 幾何生成模組（相容層/封裝）
│   │   └── __init__.py
│   │
│   ├── 📂 math/                         # 數學計算模組
│   │   ├── cst_derivatives.py           # ✅ CST導數和切線角度計算
│   │   └── section_distribution.py      # 截面分布（餘弦分布等）
│   │
│   ├── 📂 optimization/                 # 優化模組
│   │   ├── hpa_asymmetric_optimizer.py  # ✅ 主優化器（CST曲線 + VSP建模）
│   │   └── generate_final_model.py      # ✅ 最終模型生成器
│   │
│   └── 📂 utils/                        # 工具函數
│       └── cst_visualizer.py            # 視覺化工具
│
├── 📂 tests/                            # 測試代碼（已精簡）
│   ├── analyze_existing_file.py         # 使用DragAnalyzer分析vsp3檔案
│   ├── plot_side_view_curves.py         # 側視圖曲線驗證
│   ├── run_final_generator.py           # 運行最終模型生成器
│   ├── test_final_fix.py                # 完整系統測試
│   └── 📂 experimental/                 # 實驗性代碼區
│
├── 📂 scripts/                          # 可執行腳本
│   ├── main_optimization.py             # GA主優化程式（待整合）
│   ├── test_single.py                   # 單一設計測試
│   └── calc_drag_metrics.py             # 阻力計算工具
│
├── 📂 output/                           # 輸出結果
│   ├── 📂 current/                      # 當前工作檔案
│   │   └── fairing_final_complete.vsp3  # ✅ 最終驗證完成的模型
│   ├── 📂 archive/                      # 封存檔案
│   ├── 📂 plots/                        # 圖表輸出
│   └── 📂 results/                      # 分析結果CSV
│
├── 📂 docs/                             # 文檔（已精簡）
│   ├── OPENVSP_API_GUIDE.md             # OpenVSP API指南
│   ├── ParasiteDrag_API_Solution.md     # ParasiteDrag修復方案
│   ├── MAC_SETUP.md                     # macOS 安裝與環境設定
│   └── OpenVSP Python API 文檔.pdf      # 官方API PDF
│
├── 📂 archive/                          # 總歸檔區
│   ├── 📂 src_old/                      # 舊版源代碼
│   ├── 📂 tests_debug/                  # 調試測試腳本
│   ├── 📂 docs_old/                     # 舊版文檔
│   └── 📂 root_old/                     # 根目錄舊檔案
│
├── 📂 vsp_env/                          # Python虛擬環境（勿修改）
│
├── requirements.txt                     # Python 依賴
├── activate_env.sh                      # macOS/Linux 環境啟動腳本
├── activate_env.ps1                     # Windows PowerShell 環境啟動腳本
├── CLAUDE.md                            # ⭐ 主工作文檔（所有修復記錄）
├── PROJECT_STRUCTURE.md                 # 本文件
└── README.md                            # 專案說明
```

---

## ⭐ 核心模組說明

### 1. `src/optimization/hpa_asymmetric_optimizer.py`

**主優化器 - GA 的核心**

功能：

- CST 曲線生成（上下邊界獨立）
- VSP 幾何建模（Fuselage + Super Ellipse 截面）
- ZLoc 歸一化處理
- Skinning 切線角度計算（非對稱）
- 尾部單調收斂處理

關鍵類別：

```python
from optimization.hpa_asymmetric_optimizer import CST_Modeler

# 生成曲線數據
curves = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=40)
```

### 2. `src/optimization/generate_final_model.py`

**最終模型生成器**

功能：

- 調用 CST_Modeler 生成曲線
- 創建 VSP 幾何
- 設置 ParasiteDrag 參數（保存到檔案）
- 驗證模型

使用方式：

```python
from optimization.generate_final_model import generate_final_model

gene = {
    'L': 2.5, 'W_max': 0.60, 'H_top_max': 0.95, 'H_bot_max': 0.35,
    'N1': 0.5, 'N2_top': 0.7, 'N2_bot': 0.8, 'X_max_pos': 0.25, 'X_offset': 0.7
}
generate_final_model(gene, "output/model.vsp3", verbose=True)
```

### 3. `src/analysis/drag_analysis.py`

**阻力分析器 - DragAnalyzer**

功能：

- 載入 vsp3 檔案
- 執行 ParasiteDrag 分析
- 解析 CSV 結果
- 返回 Cd, CdA, Swet, Drag

使用方式：

```python
from analysis.drag_analysis import DragAnalyzer

analyzer = DragAnalyzer(output_dir="output")
result = analyzer.run_analysis("model.vsp3", velocity=6.5, rho=1.225, mu=1.7894e-5)

print(f"Cd: {result['Cd']}")
print(f"Swet: {result['Swet']} m²")
print(f"Drag: {result['Drag']} N")
```

### 4. `src/math/cst_derivatives.py`

**CST 數學計算**

功能：

- CST 導數計算
- 切線角度計算（對稱/非對稱）
- 有限差分法斜率計算

關鍵函數：

```python
from optimization.hpa_asymmetric_optimizer import CSTDerivatives

# 計算非對稱切線角度
angles = CSTDerivatives.compute_asymmetric_tangent_angles(
    x_array, z_upper_array, z_lower_array, index
)
# 返回 {'top': angle_top, 'bottom': angle_bottom}
```

---

## 🧬 基因定義（GA 輸入）

```python
gene = {
    'L': 2.5,              # 整流罩總長 [1.8 - 3.0 m]
    'W_max': 0.60,         # 最大全寬 [0.48 - 0.65 m]
    'H_top_max': 0.95,     # 上半部高度 [0.85 - 1.15 m]
    'H_bot_max': 0.35,     # 下半部高度 [0.25 - 0.50 m]
    'N1': 0.5,             # Class function N1 [0.3 - 0.7]
    'N2_top': 0.7,         # Shape function N2（上）[0.5 - 1.0]
    'N2_bot': 0.8,         # Shape function N2（下）[0.5 - 1.0]
    'X_max_pos': 0.25,     # 最大位置 [0.2 - 0.4]
    'X_offset': 0.7,       # 收縮開始位置 [0.6 - 0.8]
}
```

---

## 🚀 GA 操作流程

### 完整流程圖

```
基因(gene)
    │
    ▼
CST_Modeler.generate_asymmetric_fairing(gene)
    │
    ▼
curves數據（psi, width, z_upper, z_lower, etc.）
    │
    ▼
generate_final_model(gene, filepath)
    │
    ▼
.vsp3 檔案（含ParasiteDrag設置）
    │
    ▼
DragAnalyzer.run_analysis(filepath, velocity, rho, mu)
    │
    ▼
result = {Cd, CdA, Swet, Drag}
    │
    ▼
適應度計算 → GA選擇/交配/突變 → 下一代
```

### GA 適應度函數模板

```python
def evaluate_fitness(gene):
    """評估單個基因的適應度"""
    import os
    import sys
    sys.path.append('src')

    from optimization.generate_final_model import generate_final_model
    from analysis.drag_analysis import DragAnalyzer

    # 1. 生成模型
    filepath = f"output/ga_temp/gen_{gen}_ind_{ind}.vsp3"
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    generate_final_model(gene, filepath, verbose=False)

    # 2. 計算阻力
    analyzer = DragAnalyzer(output_dir="output/ga_temp")
    result = analyzer.run_analysis(filepath, velocity=6.5, rho=1.225, mu=1.7894e-5)

    if result is None:
        return float('inf')  # 失敗返回極大值

    # 3. 計算適應度（最小化CdA）
    cda = result['CdA']

    # 4. 硬約束檢查（如果違反返回懲罰值）
    penalty = 0
    # TODO: 添加座艙空間約束檢查

    return cda + penalty
```

---

## ✅ 已驗證的測試結果

### 阻力計算驗證（2026-01-07）

- 測試檔案：`output/current/fairing_final_complete.vsp3`
- API 結果：Cd = 0.041209
- GUI 結果：Cd = 0.04121
- **差異：0.00%** ✅

### 幾何驗證

- 上邊界最大值：0.954 m（誤差 0.4%）
- 下邊界最小值：-0.350 m（完美）
- 濕面積：5.447 m²

---

## 📝 快速使用指南

### 1. 測試現有模型的阻力

```bash
source activate_env.sh
python tests/analyze_existing_file.py
```

### 2. 生成新模型並分析

```bash
python tests/run_final_generator.py
```

### 3. 繪製側視圖曲線

```bash
python tests/plot_side_view_curves.py
```

---

## 🚨 重要提醒

1. **W_max 必須除以 2 才能用於 CST 計算 Y 座標**
2. **ZLocPercent 是百分比(0-1)，必須除以 Length**
3. **Bottom 角度需要反號（`-math.degrees(...)`）**
4. **所有模組都在 src/下，使用前需要`sys.path.append('src')`**
5. **舊檔案都在 archive/，不要使用**

---

## 🔗 相關文檔

- `CLAUDE.md` - 完整工作記錄和修復詳情
- `docs/ParasiteDrag_API_Solution.md` - ParasiteDrag API 修復方案
- `docs/OPENVSP_API_GUIDE.md` - OpenVSP API 使用指南
