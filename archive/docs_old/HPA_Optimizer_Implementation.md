# HPA 非對稱整流罩優化器 - 實作文檔

**創建日期**: 2026-01-04
**最後更新**: 2026-01-04 21:10
**狀態**: ✅ 已修正並測試通過（等待用戶驗證 VSP 模型）

---

## 1. 當前問題清單

### 問題 1: 截面位置分布錯誤 ❌
**症狀**: 使用線性分布 `np.linspace(0, 1, num_sections)`
**應該**: 使用餘弦分布 `SectionDistribution.cosine_full()`
**影響**: 機頭和機尾截面太稀疏，阻力計算不準確
**位置**: `src/optimization/hpa_asymmetric_optimizer.py:141`

### 問題 2: 缺少切線角度計算 ❌
**症狀**: 完全沒有設置 `SetXSecTanAngles()`
**應該**: 使用 `CSTDerivatives.compute_tangent_angles_for_section()` 計算並設置切線
**影響**: VSP skinning 不正確，表面不光滑
**位置**: `src/optimization/hpa_asymmetric_optimizer.py:285-311`

### 問題 3: 上下非對稱未正確實現 ❌
**症狀**: 模型看起來上下對稱
**原因**: VSP Super_Ellipse 只能設置一個高度值，上下高度被平均了
**應該**:
- 方案 A: 使用 Stack 組合上下兩個不同的 Fuselage
- 方案 B: 使用自定義截面（更複雜）
- 方案 C: 在 CST 曲線階段就分開處理，生成兩條高度曲線後再合併
**位置**: `src/optimization/hpa_asymmetric_optimizer.py:302-305`

### 問題 4: CST 公式可能不正確 ⚠️
**症狀**: 需要驗證上下分開的 CST 曲線是否正確
**位置**: `src/optimization/hpa_asymmetric_optimizer.py:144-161`

---

## 2. 專案中已有的工具（必須使用）

### 2.1 截面分布生成器
**檔案**: `src/math/section_distribution.py`
**類別**: `SectionDistribution`

**方法**:
```python
# 全餘弦分布（推薦）
psi_values = SectionDistribution.cosine_full(num_sections=40, min_spacing=0.001)

# 機頭密集分布
psi_values = SectionDistribution.cosine_nose_only(num_sections, min_spacing)

# 機尾密集分布
psi_values = SectionDistribution.cosine_tail_only(num_sections, min_spacing)

# 均勻分布（不推薦用於阻力分析）
psi_values = SectionDistribution.uniform(num_sections)
```

**公式**:
- 全餘弦: `psi = 0.5 * (1 - cos(π * i / (n-1)))`
- 特點: 機頭和機尾密集，中間稀疏

### 2.2 CST 導數計算引擎
**檔案**: `src/math/cst_derivatives.py`
**類別**: `CSTDerivatives`

**主要方法**:
```python
# 計算 CST 半徑
r = CSTDerivatives.cst_radius(psi, N1, N2, weights, length)

# 計算切線角度（用於 skinning）
angles = CSTDerivatives.compute_tangent_angles_for_section(
    psi, N1, N2,
    width_weights,
    height_weights,
    length
)
# 返回: {'top': angle, 'right': angle, 'bottom': angle, 'left': angle}

# 計算機頭切線角度
nose_angle = CSTDerivatives.tangent_angle_at_nose(N1, N2, weights)
```

**用途**: 確保 VSP skinning 正確，避免表面扭曲

### 2.3 已驗證的 VSP 模型生成器
**檔案**: `src/geometry/cst_geometry_math_driven.py`
**類別**: `CSTGeometryMathDriven`

**關鍵步驟**（必須遵循）:
1. 使用餘弦分布生成截面位置
2. 插入截面後設置幾何尺寸
3. **設置切線角度**（重要！）:
   ```python
   vsp.SetXSecContinuity(xsec, continuity)  # C1 連續性
   vsp.SetXSecTanAngles(xsec, vsp.XSEC_BOTH_SIDES, top, right, bottom, left)
   vsp.SetXSecTanStrengths(xsec, vsp.XSEC_BOTH_SIDES, 0.75, 0.75, 0.75, 0.75)
   vsp.SetXSecTanSlews(xsec, vsp.XSEC_BOTH_SIDES, 0.0, 0.0, 0.0, 0.0)
   ```
4. 設置 ParasiteDrag 參數（保存前）

### 2.4 已驗證的阻力分析器
**檔案**: `src/analysis/drag_analysis.py`
**類別**: `DragAnalyzer`

**用法**:
```python
analyzer = DragAnalyzer(output_dir="output")
result = analyzer.run_analysis(vsp_file, velocity=6.5, rho=1.225, mu=1.7894e-5)
# 返回: {'Cd': cd, 'Swet': swet, 'CdA': cda}
```

---

## 3. HPA 優化器檔案結構

### 主檔案: `src/optimization/hpa_asymmetric_optimizer.py`

**類別結構**:
```
ProjectManager          # 專案檔案管理
├── __init__()         # 創建時間戳目錄
├── log()              # 日誌記錄
├── save_gene()        # 保存基因
└── save_best_gene()   # 保存最佳基因

CST_Modeler            # CST 幾何建模器（手寫公式）
├── class_function()   # C(ψ) = ψ^N1 * (1-ψ)^N2
├── shape_function()   # S(ψ) = Σ(w_i * Bernstein_i)
├── cst_curve()        # η(ψ) = max * SF * C * S
└── generate_asymmetric_fairing()  # 生成非對稱曲線

ConstraintChecker      # 硬限制檢查器
├── check_all_constraints()  # 檢查所有限制
└── interpolate_curve()      # 插值輔助

VSPModelGenerator      # VSP 模型生成器 ❌ 需要修正
├── create_fuselage()  # 從曲線創建 VSP 模型
└── [需要添加切線計算和設置]

HPA_Optimizer          # 優化器主類
├── evaluate_individual()  # 評估單個個體
├── gene_to_array()        # 基因轉換
└── array_to_gene()

run_ga_optimization()  # GA 優化主函數（使用 pymoo）
run_test_mode()        # 測試模式
```

### 輸出目錄結構:
```
output/
└── hpa_run_YYYYMMDD_HHMMSS/
    ├── vsp_models/              # VSP 檔案和 CSV
    │   ├── gen000_ind000.vsp3
    │   ├── gen000_ind000_ParasiteBuildUp.csv
    │   └── ...
    ├── drag_csv/                # 預留（未使用）
    └── logs/
        ├── optimization_log.txt # 運行日誌
        └── best_gene.json       # 最佳基因
```

---

## 4. 基因參數定義

### 9 個優化變數:

| 參數 | 範圍 | 說明 |
|------|------|------|
| `L` | (1.8, 3.0) m | 總長度 |
| `W_max` | (0.48, 0.65) m | 最大寬度 |
| `H_top_max` | (0.85, 1.15) m | 上部最大高度 |
| `H_bot_max` | (0.25, 0.50) m | 下部最大高度 |
| `N1` | (0.4, 0.9) | 機頭形狀係數 |
| `N2_top` | (0.5, 1.0) | 上機尾形狀係數 |
| `N2_bot` | (0.5, 1.0) | 下機尾形狀係數 |
| `X_max_pos` | (0.2, 0.5) | 最大截面位置 (0-1) |
| `X_offset` | (0.5, 1.0) m | 踏板位置 |

### 硬限制:

1. **車架包覆**: `X_offset - 0.3 >= 0`
2. **踏板寬度**: `w(X_offset) >= 0.45 m`
3. **肩膀寬度**: `w(X_offset + 0.5) >= 0.52 m`
4. **肩膀上高**: `h_top(X_offset + 0.5) >= 0.75 m`
5. **肩膀下高**: `h_bot(X_offset + 0.5) >= 0.25 m`
6. **機尾長度**: `L - X_offset >= 1.5 m`

---

## 5. 測試結果（當前版本）

### 測試模式:
- ✅ VSP 模型生成成功
- ✅ ParasiteDrag 分析成功
- ✅ 阻力計算: 2.28 N
- ❌ 但模型不正確（沒有上下非對稱，沒有正確 skinning）

### GA 優化 (2代, 5個體):
- 總評估: 10 個
- 成功: 6 個 (60%)
- 失敗: 4 個 (40%, 限制失敗)
- 最佳阻力: 2.32 N (第2代)
- ❌ 但基於錯誤的模型

---

## 6. 需要的修正清單

### 修正 1: 截面分布 (高優先級)
**檔案**: `src/optimization/hpa_asymmetric_optimizer.py`

**修改位置**: `CST_Modeler.generate_asymmetric_fairing()` 方法

**修改前**:
```python
psi = np.linspace(0, 1, num_sections)
```

**修改後**:
```python
from math.section_distribution import SectionDistribution
psi_list = SectionDistribution.cosine_full(num_sections, min_spacing=0.001)
psi = np.array(psi_list)
```

### 修正 2: 添加切線角度計算 (高優先級)
**檔案**: `src/optimization/hpa_asymmetric_optimizer.py`

**修改位置**: `VSPModelGenerator.create_fuselage()` 方法的截面設置循環

**需要添加**:
```python
from math.cst_derivatives import CSTDerivatives

# 在設置幾何尺寸後添加:
if not is_tip:
    # ... 現有的幾何設置 ...

    # 計算切線角度（新增）
    tangent_angles = CSTDerivatives.compute_tangent_angles_for_section(
        psi,
        gene['N1'],
        (gene['N2_top'] + gene['N2_bot']) / 2.0,  # 暫時用平均值
        np.array([0.25, 0.35, 0.30, 0.10]),  # width weights
        np.array([0.25, 0.35, 0.30, 0.10]),  # height weights
        curves['L']
    )

    # 設置切線（新增）
    vsp.SetXSecContinuity(xsec, 1)  # C1
    vsp.SetXSecTanAngles(
        xsec, vsp.XSEC_BOTH_SIDES,
        tangent_angles['top'],
        tangent_angles['right'],
        tangent_angles['bottom'],
        tangent_angles['left']
    )
    vsp.SetXSecTanStrengths(xsec, vsp.XSEC_BOTH_SIDES, 0.75, 0.75, 0.75, 0.75)
    vsp.SetXSecTanSlews(xsec, vsp.XSEC_BOTH_SIDES, 0.0, 0.0, 0.0, 0.0)
```

### 修正 3: 上下非對稱實現 (關鍵問題)
**問題**: VSP Super_Ellipse 只有一個 `Super_Height` 參數

**方案 A - 使用平均高度 + Z偏移** (簡單):
```python
# 計算平均高度和偏移
height_top = curves['top'][i]
height_bot = abs(curves['bottom'][i])
height_avg = (height_top + height_bot) / 2.0
z_offset = (height_top - height_bot) / 2.0

# 設置高度
vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Height"), height_avg)

# 設置 Z 偏移（如果有這個參數）
# TODO: 需要確認 VSP API 是否支持截面 Z 偏移
```

**方案 B - Stack 組合** (複雜但準確):
- 生成上半部 Fuselage (使用 H_top)
- 生成下半部 Fuselage (使用 H_bot)
- 使用 Stack 組合
- 需要大幅修改代碼結構

**方案 C - 先測試對稱版本** (推薦):
- 先確保餘弦分布和切線角度正確
- 使用平均高度生成對稱模型
- 驗證 skinning 和阻力計算正確
- 再解決非對稱問題

### 修正 4: 機頭機尾特殊處理
**需要添加機頭切線角度**:
```python
if i == 0:
    # 機頭
    nose_angle = CSTDerivatives.tangent_angle_at_nose(
        gene['N1'],
        (gene['N2_top'] + gene['N2_bot']) / 2.0,
        np.array([0.25, 0.35, 0.30, 0.10])
    )
    vsp.SetXSecContinuity(xsec, 1)
    vsp.SetXSecTanAngles(xsec, vsp.XSEC_BOTH_SIDES,
                        nose_angle, nose_angle, nose_angle, nose_angle)
    vsp.SetXSecTanStrengths(xsec, vsp.XSEC_BOTH_SIDES, 0.75, 0.75, 0.75, 0.75)
```

---

## 7. 修正優先級

1. **立即修正** (阻礙測試):
   - [ ] 截面分布改用餘弦分布
   - [ ] 添加切線角度計算和設置

2. **先用簡化版測試** (驗證方法):
   - [ ] 使用平均高度（暫時忽略上下非對稱）
   - [ ] 測試 VSP 模型是否正確
   - [ ] 測試阻力計算是否準確

3. **後續改進** (完整功能):
   - [ ] 實現真正的上下非對稱
   - [ ] 優化 GA 參數
   - [ ] 增加更多限制檢查

---

## 8. 參考檔案

- `src/geometry/cst_geometry_math_driven.py` - 已驗證的 VSP API 模式（必須參考）
- `src/math/section_distribution.py` - 截面分布生成器
- `src/math/cst_derivatives.py` - 切線角度計算
- `src/analysis/drag_analysis.py` - 阻力分析器
- `docs/ParasiteDrag_API_Solution.md` - ParasiteDrag 問題解決方案

---

## 9. 下一步行動

**用戶要求**:
> "先把這部分用好(帶固定的參數進去)，先不要跑GA，等ok了我們再試"

**行動計劃**:
1. 創建測試腳本 `tests/test_hpa_model_generation.py`
2. 使用固定參數生成單個模型
3. 驗證:
   - ✅ 餘弦分布截面
   - ✅ 切線角度正確
   - ✅ VSP 模型可視化正確
   - ✅ 阻力值合理
4. 確認無誤後才運行 GA

---

**最後更新**: 2026-01-04
**狀態**: 等待修正

---

## 10. 修正測試結果 (2026-01-04 21:10)

### 已完成的修正:

1. **✅ 截面分布改用餘弦分布**
   - 修改位置：`CST_Modeler.generate_asymmetric_fairing()`
   - 使用：`SectionDistribution.cosine_full(num_sections, min_spacing=0.001)`
   - 結果：間距比率 24.83x（機頭機尾密集）

2. **✅ 添加切線角度計算和設置**
   - 修改位置：`VSPModelGenerator.create_fuselage()`
   - 使用：`CSTDerivatives.compute_tangent_angles_for_section()`
   - 設置：`SetXSecTanAngles()`, `SetXSecTanStrengths()`, `SetXSecTanSlews()`
   - 包含機頭特殊處理：`tangent_angle_at_nose()`

3. **✅ 暫時使用平均高度（對稱版本）**
   - `height_avg = (height_top + height_bot) / 2.0`
   - 目的：先驗證餘弦分布和切線角度正確

### 測試腳本:
- **主測試**：`tests/test_hpa_fixed_params.py`
- **結果查看**：`tests/view_test_results.py`

### 測試結果（固定參數）:

**基因參數**:
```python
{
    'L': 2.5 m,
    'W_max': 0.60 m,
    'H_top_max': 0.95 m,
    'H_bot_max': 0.35 m,
    'N1': 0.5,
    'N2_top': 0.7,
    'N2_bot': 0.8,
    'X_max_pos': 0.25,
    'X_offset': 0.7 m
}
```

**截面分布驗證**:
- ✅ 截面數量：40
- ✅ 餘弦分布：間距比率 24.83x
- ✅ 前 5 個 psi: [0.000000, 0.001621, 0.006475, 0.014529, 0.025732]
- ✅ 機頭機尾密集 ✅

**限制檢查**:
- ✅ 車架包覆：0.400 m
- ✅ 踏板寬度：0.619 m (>= 0.450 m required)
- ✅ 肩膀寬度：0.618 m (>= 0.520 m required)
- ✅ 肩膀上高：0.996 m (>= 0.750 m required)
- ✅ 肩膀下高：0.354 m (>= 0.250 m required)
- ✅ 機尾長度：1.800 m (>= 1.500 m required)
- **所有6項限制全部通過** ✅✅✅

**VSP 模型**:
- ✅ 檔案：`output/test_hpa_fixed_params.vsp3`
- ✅ 大小：687 KB
- ✅ 含餘弦分布截面
- ✅ 含切線角度設置
- ⚠️ 需要用戶用 GUI 驗證形狀

**阻力計算**:
- ✅ **Swet = 3.746 m²**
- ✅ **Cd = 0.023354**
- ✅ **Drag = 2.26 N**

### 待驗證項目:

**用戶需要檢查**（用 OpenVSP GUI）:
1. [ ] 截面是否在機頭機尾密集？（餘弦分布）
2. [ ] 表面是否光滑無扭曲？（切線角度正確）
3. [ ] 整體形狀是否合理？
4. [ ] 是否需要調整上下非對稱？

### 下一步（等用戶驗證後）:

**如果 VSP 模型正確**：
- 可以開始運行 GA 優化
- 指令：`python src/optimization/hpa_asymmetric_optimizer.py --mode ga --gen 10 --pop 20`

**如果需要改進**：
- 實現真正的上下非對稱（目前用平均高度）
- 調整測試參數
- 優化限制條件

---

**測試完成時間**: 2026-01-04 21:10
**狀態**: 等待用戶驗證 VSP 模型視覺效果
