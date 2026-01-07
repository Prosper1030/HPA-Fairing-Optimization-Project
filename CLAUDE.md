# HPA整流罩優化器 - Claude工作文檔

**最後更新：2026-01-07**

---

## 📋 當前任務狀態

### ✅ 已完成（2026-01-07更新）
1. CST曲線峰值歸一化實現
2. 側視圖上下邊界獨立反推法（Python驗證完成）
3. ParasiteDrag API修復
4. 餘弦分布截面生成
5. **應用新幾何定義到VSP（ZLoc歸一化修復）** ✅
6. **Skinning切線角度完整修復（非對稱角度計算法 + Bottom正負號修正）** ✅
7. **Nose/Tail截面角度修復（統一使用新方法）** ✅
8. **尾部單調收斂修復（避免扭曲）** ✅
9. **Output資料夾結構化整理** ✅
10. **DragAnalyzer CSV路徑修復（完美匹配GUI結果，差異0.00%）** ✅

### 📝 待辦
- GA優化器整合
- 硬約束驗證
- 完整參數空間測試

---

## 🧬 基因定義（9個變數）

### 關鍵澄清（避免歧義）

**W_max：最大全寬 (Full Width)**
- 範圍：[0.48 - 0.65 m]
- **⚠️ 重要：在代入CST計算時，必須除以2！**
- 原因：CST計算Y座標時需要半寬（radius）

**H_top_max：上半部高度 (Upper Radius)**
- 範圍：[0.85 - 1.15 m]
- **已經是半徑，直接使用**
- 對應手繪圖的上半部空間需求

**H_bot_max：下半部高度 (Lower Radius)**
- 範圍：[0.25 - 0.50 m]
- **已經是半徑，直接使用**
- 對應手繪圖的下半部空間需求

### 完整基因列表

```python
gene = {
    'L': 2.5,              # 整流罩總長 [1.8 - 3.0 m]
    'W_max': 0.60,         # 最大全寬 (Full Width) [0.48 - 0.65 m]
    'H_top_max': 0.95,     # 上半部高度 (Upper Radius) [0.85 - 1.15 m]
    'H_bot_max': 0.35,     # 下半部高度 (Lower Radius) [0.25 - 0.50 m]
    'N1': 0.5,             # Class function N1 [0.3 - 0.7]（上下共用）
    'N2_top': 0.7,         # Shape function N2（上）[0.5 - 1.0]
    'N2_bot': 0.8,         # Shape function N2（下）[0.5 - 1.0]
    'X_max_pos': 0.25,     # 最大寬度/高度位置 [0.2 - 0.4]
    'X_offset': 0.7,       # 收縮開始位置 [0.6 - 0.8]
}
```

---

## 📐 幾何定義：上下邊界獨立反推法

### 座標系
- **XZ平面**：側視圖
- **原點(0,0)**：機頭最尖端
- **X軸**：向後（機身方向）
- **Z軸**：向上（垂直方向）

### 幾何特徵

**1. 機頭行為：**
- 起點：上下邊界都在(0, 0)
- 指向性：機頭必須指向「正前方」
- 實現：上下邊界使用相同的N1，確保在原點附近對稱於X軸

**2. 上邊界曲線（Upper Curve）：**
- 從(0, 0)出發
- 向上拱起，最高點約H_top_max
- 平滑收束於機尾點(L, Tail_Rise)

**3. 下邊界曲線（Lower Curve）：**
- 從(0, 0)出發
- 向下包覆，最低點約-H_bot_max
- 經過最低點後，俐落向上斜切，追蹤機尾點(L, Tail_Rise)
- **關鍵**：避免下垂的"肚腩"

**4. 機尾行為：**
- 上下曲線在(L, Tail_Rise)完美交會成尖點
- 封閉性：該點厚度為0

### 數學公式

**CST曲線生成：**
```python
z_upper_cst = CST_Modeler.cst_curve(psi, H_top_max, N1, N2_top, weights)
z_lower_cst = -CST_Modeler.cst_curve(psi, H_bot_max, N1, N2_bot, weights)
```

**混合到機尾：**
```python
# 混合因子（從blend_start=0.75開始）
blend_factor = 0  # for psi < 0.75
blend_factor = ((psi - 0.75) / 0.25)^2  # for psi >= 0.75

# 混合曲線
z_upper = z_upper_cst * (1 - blend_factor) + Tail_Rise * blend_factor
z_lower = z_lower_cst * (1 - blend_factor) + Tail_Rise * blend_factor
```

**反推VSP參數：**
```python
Super_Height = z_upper - z_lower  # 總厚度
Z_Loc = (z_upper + z_lower) / 2   # 幾何中心（用於ZLocPercent）
```

---

## 🔧 VSP實現細節

### 截面類型
- 機頭（i=0）：`XS_POINT`
- 中間截面：`XS_SUPER_ELLIPSE`
- 機尾（i=num_sections-1）：`XS_POINT`

### 關鍵參數設置

**幾何參數：**
```python
vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Width"), total_width)
vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Height"), total_height)
vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_M"), 2.5)
vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_N"), 2.5)
```

**Z位置設置：**
```python
z_loc_parm = vsp.GetXSecParm(xsec, "ZLocPercent")
if z_loc_parm:
    vsp.SetParmVal(z_loc_parm, z_loc)  # 使用計算的幾何中心
```

**Skinning切線角度（需要調整）：**
```python
# ⚠️ 待實現：上下分開計算
tangent_top = compute_tangent(psi, N1, N2_top, ...)     # 上曲線
tangent_bot = compute_tangent(psi, N1, N2_bot, ...)     # 下曲線
tangent_lr = compute_tangent(psi, N1, N2_avg, ...)      # 左右對稱

vsp.SetXSecTanAngles(
    xsec, vsp.XSEC_BOTH_SIDES,
    tangent_top['top'],      # 上
    tangent_lr['right'],     # 右
    tangent_bot['bottom'],   # 下
    tangent_lr['left']       # 左
)
```

---

## 🎯 硬約束

### 座艙空間約束
```python
def check_cockpit_clearance(curves, gene):
    # 騎乘姿勢中心點
    rider_center = (1.2, 0.0, 0.40)

    # 檢查點
    checks = {
        'head': (0.9, 0.0, 0.90),      # 頭部
        'shoulder_L': (1.0, -0.23, 0.75),
        'shoulder_R': (1.0, 0.23, 0.75),
        'knee_L': (1.5, -0.15, 0.25),
        'knee_R': (1.5, 0.15, 0.25),
    }
```

### 腳踏寬度約束
- 腳踏寬度W_pedal ≈ 0.16 m
- 約束：curves['width_half'] >= W_pedal/2 + clearance

---

## 📊 已驗證的結果

### 側視圖曲線（Python測試）
- 上邊界最大值：0.954 m（誤差 0.4%）
- 下邊界最小值：-0.350 m（完美）
- 機頭閉合：0.000 m
- 機尾閉合：0.000 m

### CST峰值歸一化（之前測試）
- 寬度誤差：0.15%
- 高度誤差：0.14%

### Skinning角度修復（2026-01-06）✅
- **方法**：使用有限差分法直接從z_upper/z_lower曲線計算斜率
- **機頭/機尾**：使用新的非對稱角度計算法（取代舊的CST導數法）
- **Bottom角度**：加入負號修正以符合VSP定義
- **尾部收斂**：單調插值避免扭曲
- **結果**：所有截面（包括機頭機尾）的上下表面完全平滑
- 驗證檔案：`output/current/fairing_final_complete.vsp3`

### 阻力計算結果（2026-01-06）✅
**測試條件**：
- 速度：15 m/s
- 溫度：20°C (293K)
- 壓力：1 atm (101325 Pa)
- 密度：ρ = 1.204 kg/m³

**幾何參數**：
- 投影面積（正面）：0.615 m²
- 濕潤表面積：12.339 m²
- 最大寬度：0.601 m
- 總高度：1.303 m

**阻力結果**：
- **阻力面積 CdA：0.873 m²**
- **阻力係數 Cd：1.420**（基於投影面積）
- **阻力計數：14200 counts**
- **阻力力量：118.3 N** @ 15 m/s

**計算檔案**：`tests/parse_drag_results.py`
**CSV結果**：`Unnamed_ParasiteBuildUp.csv`

---

## 🔧 最新修復記錄（2026-01-06）

### 問題1：ZLoc位置問題（⚠️ 關鍵修復）
**現象**：模型在VSP中位置偏移，整個fairing太高，下邊界無法到達負值
**根本原因**：**ZLocPercent是百分比（0-1範圍），不是絕對座標！**
**解決**：
```python
# 在 hpa_asymmetric_optimizer.py:470-475
# ❌ 錯誤：直接使用絕對值
# vsp.SetParmVal(z_loc_parm, z_loc_value)

# ✅ 正確：除以長度歸一化
z_loc_normalized = z_loc_value / curves['L']  # 歸一化到0-1範圍
vsp.SetParmVal(z_loc_parm, z_loc_normalized)
```
**驗證方法**：生成3個測試檔案對比（絕對值/歸一化/全0），確認歸一化版本正確
**最終檔案**：`output/test_new_geometry.vsp3`

### 問題2：Skinning角度計算錯誤（⚠️ 關鍵修復）
**現象**：上下表面skinning不平滑，特別是後段區域
**錯誤嘗試**：調整Strength參數（無效）
**根本原因**：舊的`compute_tangent_angles_for_section`函數是為**對稱幾何**設計的，對非對稱上下邊界計算錯誤
**正確解法**：直接從z_upper和z_lower曲線使用有限差分法計算斜率

**新增函數** (`cst_derivatives.py:232-281`)：
```python
@staticmethod
def compute_asymmetric_tangent_angles(x_array, z_upper_array, z_lower_array, index):
    """直接從z_upper和z_lower曲線的斜率計算切線角度"""
    # 使用有限差分計算斜率
    if index == 0:
        # 前向差分
        dz_upper_dx = (z_upper_array[1] - z_upper_array[0]) / (x_array[1] - x_array[0])
        dz_lower_dx = (z_lower_array[1] - z_lower_array[0]) / (x_array[1] - x_array[0])
    elif index == n - 1:
        # 後向差分
        dz_upper_dx = (z_upper_array[index] - z_upper_array[index-1]) / ...
        dz_lower_dx = (z_lower_array[index] - z_lower_array[index-1]) / ...
    else:
        # 中心差分（更準確）
        dz_upper_dx = (z_upper_array[index+1] - z_upper_array[index-1]) / ...
        dz_lower_dx = (z_lower_array[index+1] - z_lower_array[index-1]) / ...

    # 轉換為角度
    angle_top = math.degrees(math.atan(dz_upper_dx))
    # ⚠️ 關鍵：Bottom需要反號以符合VSP定義！
    angle_bottom = -math.degrees(math.atan(dz_lower_dx))

    return {'top': angle_top, 'bottom': angle_bottom}
```

**應用到VSP** (`hpa_asymmetric_optimizer.py:493-499, 532-545`)：
```python
# 中間截面
asymmetric_angles = CSTDerivatives.compute_asymmetric_tangent_angles(
    curves['x'], curves['z_upper'], curves['z_lower'], i
)
angle_top_use = asymmetric_angles['top']
angle_bot_use = asymmetric_angles['bottom']

# 機頭/機尾也使用相同方法
nose_angles = CSTDerivatives.compute_asymmetric_tangent_angles(
    curves['x'], curves['z_upper'], curves['z_lower'], 0
)
vsp.SetXSecTanAngles(xsec, vsp.XSEC_BOTH_SIDES,
    nose_angles['top'], angle_lr, nose_angles['bottom'], angle_lr
)
```

**驗證檔案**：`output/current/fairing_complete_angle_fix.vsp3`

### 問題3：尾部扭曲（⚠️ 關鍵修復）
**現象**：尾部截面和曲線扭曲，skinning線條不平滑，上曲線先降後升
**根本原因**：線性混合策略讓z_upper降到tail_rise以下後再上升，造成拐點
**分析**：
- 混合前：z_upper_cst在截面35降到0.0929（低於tail_rise=0.1）
- 混合後：z_upper在截面36-38上升回0.1（形成凸起）
- 結果：角度從負變正，造成S型曲線和扭曲

**解決方案**：找到曲線接近tail_rise的點（10%容差內），從該點開始強制線性插值
```python
# 在 hpa_asymmetric_optimizer.py:239-262
# 找第一個降到接近 tail_rise 的點
tolerance = tail_rise * 1.10  # tail_rise + 10%
for i, idx in enumerate(blend_indices):
    if z_upper[idx] <= tolerance:
        linear_start_idx_upper = i
        break

# 從該點開始強制線性插值到 tail_rise
if linear_start_idx_upper is not None:
    start_idx = blend_indices[linear_start_idx_upper]
    start_z = z_upper[start_idx]
    start_psi = psi[start_idx]

    # 確保起點不低於 tail_rise（避免上升）
    if start_z < tail_rise:
        start_z = tail_rise

    for i in range(linear_start_idx_upper, len(blend_indices)):
        idx = blend_indices[i]
        t = (psi[idx] - start_psi) / (1.0 - start_psi)
        z_upper[idx] = start_z + (tail_rise - start_z) * t
```

**結果**：
- 截面34-38：z_upper = 0.1000（保持常數）
- 上下曲線完全單調收斂✅
- 尾部平滑無扭曲✅

**驗證檔案**：`output/current/fairing_tail_fixed.vsp3`, `output/current/fairing_final_complete.vsp3`

### 問題4：Output資料夾混亂
**解決**：建立結構化資料夾
```
output/
├── current/      # 當前工作檔案（最新版本）
├── archive/      # 舊測試檔案（39個）
├── results/      # CompGeom/ParasiteDrag結果（50個）
├── plots/        # 圖片（13個）
├── temp/         # 臨時.fxs檔案（40個）
└── hpa_run_*/    # GA運行資料夾
```

### 問題5：DragAnalyzer找不到CSV檔案（⚠️ 關鍵修復 2026-01-07）
**現象**：
- ParasiteDrag執行成功，CD值正確（0.041209 ≈ GUI的0.04121）
- 但DragAnalyzer報錯："Analysis CSV not found, analysis may have failed"
- 阻力計算結果錯誤：Swet = 2.03 m²（應為5.447 m²）

**根本原因**：
- VSP生成CSV檔案在**vsp檔案所在目錄**，不是當前工作目錄
- 例如：`output/current/fairing_final_complete_ParasiteBuildUp.csv`
- DragAnalyzer只檢查當前目錄和output目錄，找不到vsp檔案所在目錄的CSV

**解決方案** (`drag_analysis.py:64-77`)：
```python
# 原本邏輯
if os.path.exists(generated_csv):
    shutil.move(generated_csv, target_csv)
elif not os.path.exists(target_csv):
    print("❌ Analysis CSV not found")
    return None

# ✅ 修復後：增加檢查vsp檔案所在目錄
if os.path.exists(generated_csv):
    shutil.move(generated_csv, target_csv)
else:
    # 檢查vsp檔案所在目錄
    vsp_dir = os.path.dirname(vsp_filepath)
    vsp_dir_csv = os.path.join(vsp_dir, generated_csv)

    if os.path.exists(vsp_dir_csv):
        # 從vsp目錄移動到output目錄
        if os.path.exists(target_csv):
            os.remove(target_csv)
        shutil.move(vsp_dir_csv, target_csv)
    elif not os.path.exists(target_csv):
        print("❌ Analysis CSV not found")
        return None
```

**驗證結果** (`tests/analyze_existing_file.py`)：
```
✅ 成功解析CSV！

Cd: 0.041209
CdA: 0.041209 m²
Swet: 5.447283 m²
Drag: 1.066 N

與GUI對比：
  GUI CD: 0.04121
  API CD: 0.041209
  差異: 0.00%  ✅ 完美匹配！
```

**關鍵改進**：
- 修復前：Swet = 2.03 m²（只有37%）❌
- 修復後：Swet = 5.447 m²（完整濕面積）✅
- 與GUI差異：從原本的巨大誤差改為 **0.00%** ✅

**測試檔案**：`output/current/fairing_final_complete.vsp3`

---

## 🚨 重要提醒

1. **W_max必須除以2才能用於CST計算Y座標**
2. **H_top_max和H_bot_max已經是半徑，直接使用**
3. **機頭對稱：上下必須使用相同的N1**
4. **Skinning：對稱截面使用N2_avg，非對稱截面分開使用N2_top/N2_bot**
5. **⚠️ ZLocPercent必須除以Length！（是0-1的百分比，不是絕對座標）**
6. **所有參數都支持GA調整，確保算法完全參數化**

---

## 📁 重要文件

### 核心程式
- `src/optimization/hpa_asymmetric_optimizer.py`：主優化器（包含ZLoc和Skinning修復）
- `src/math/cst_derivatives.py`：CST導數計算

### 測試腳本
- `tests/plot_side_view_curves.py`：側視圖驗證
- `tests/test_zloc_fixed_v2.py`：ZLoc修復驗證
- `tests/test_skinning_fixed.py`：Skinning角度驗證
- `tests/diagnose_skinning_angles.py`：角度診斷工具

### 當前工作檔案
- `output/current/fairing_zloc_fixed_v2.vsp3`：ZLoc修復版本
- `output/current/fairing_skinning_fixed.vsp3`：Skinning修復版本
- `output/plots/side_view_curves.png`：側視圖結果

### 文檔
- `CLAUDE.md`：本文件（工作記錄）
- `docs/implementation_log.md`：詳細實現日誌
