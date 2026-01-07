# OpenVSP ParasiteDrag API 問題解決方案

## 問題描述

### 症狀
使用 OpenVSP Python API 執行 ParasiteDrag 分析時遇到以下問題：

1. **CD 值錯誤**：API 計算的 CD = 0.000357，而 GUI 計算的 CD = 0.02045（差異 98%）
2. **濕面積不匹配**：
   - CompGeom 計算：3.368 m² ✅
   - ParasiteDrag 使用：1.253 m² ❌（只有 37%）
3. **警告訊息**：`Warning: Geom ID not included in Parasite Drag calculation`
4. **CSV 單位錯誤**：生成的 CSV 使用英制單位（ft, lbf/ft²），而非公制

### 根本原因

**VSP 文件中保存的 ParasiteDrag 設置是錯誤的單位和數值：**

```xml
<ParasiteDragMgr>
  <Sref Value="1.000000000000000000e+02"/>  <!-- 100 ft²，應該是 1.0 m² -->
  <LengthUnit Value="4.000000000000000000e+00"/>  <!-- 英制，應該是 2 (meters) -->
  <Alt Value="2.000000000000000000e+04"/>  <!-- 20000 ft，應該是 0 m -->
  <Vinf Value="5.000000000000000000e+02"/>  <!-- 500 ft/s，應該是 6.5 m/s -->
  <TurbCfEqnType Value="1.000000000000000000e+01"/>  <!-- 10，應該是 7 -->
</ParasiteDragMgr>
```

**為什麼會有問題：**
1. `vsp.SetAnalysisInput()` **只設置運行時參數**，不會保存到 VSP 文件
2. 簡單的 API 調用（如 `drag_analysis.py`）依賴文件中保存的設置
3. 新生成的 VSP 文件使用 OpenVSP 的預設值（英制單位）

## 解決方案

### 關鍵發現

**必須直接修改 ParasiteDragSettings 容器中的 Parm 值**，這樣設置才會被保存到 VSP 文件中。

### 實現方法

在 `cst_geometry_math_driven.py` 中，保存 VSP 文件之前：

```python
# 找到 ParasiteDragSettings 容器
pd_container = vsp.FindContainer("ParasiteDragSettings", 0)

if pd_container:
    # 設置單位為公制（LengthUnit = 2 = meters）
    length_unit_parm = vsp.FindParm(pd_container, "LengthUnit", "ParasiteDrag")
    if length_unit_parm:
        vsp.SetParmVal(length_unit_parm, 2.0)  # LEN_M = 2

    # 設置參考面積為 1.0 m²
    sref_parm = vsp.FindParm(pd_container, "Sref", "ParasiteDrag")
    if sref_parm:
        vsp.SetParmVal(sref_parm, 1.0)

    # 設置高度為 0（海平面）
    alt_parm = vsp.FindParm(pd_container, "Alt", "ParasiteDrag")
    if alt_parm:
        vsp.SetParmVal(alt_parm, 0.0)

    # 設置高度單位為 meters
    alt_unit_parm = vsp.FindParm(pd_container, "AltLengthUnit", "ParasiteDrag")
    if alt_unit_parm:
        vsp.SetParmVal(alt_unit_parm, 1.0)

    # 設置速度為 6.5 m/s
    vinf_parm = vsp.FindParm(pd_container, "Vinf", "ParasiteDrag")
    if vinf_parm:
        vsp.SetParmVal(vinf_parm, 6.5)

    # 設置速度單位為 m/s
    vinf_unit_parm = vsp.FindParm(pd_container, "VinfUnitType", "ParasiteDrag")
    if vinf_unit_parm:
        vsp.SetParmVal(vinf_unit_parm, 1.0)

    # 設置溫度為 15°C
    temp_parm = vsp.FindParm(pd_container, "Temp", "ParasiteDrag")
    if temp_parm:
        vsp.SetParmVal(temp_parm, 15.0)

    # 設置溫度單位為 Celsius
    temp_unit_parm = vsp.FindParm(pd_container, "TempUnit", "ParasiteDrag")
    if temp_unit_parm:
        vsp.SetParmVal(temp_unit_parm, 1.0)

    # 設置層流摩擦係數方程式為 Blasius (0)
    lam_cf_parm = vsp.FindParm(pd_container, "LamCfEqnType", "ParasiteDrag")
    if lam_cf_parm:
        vsp.SetParmVal(lam_cf_parm, 0.0)

    # 設置紊流摩擦係數方程式為 Power Law Prandtl Low Re (7)
    turb_cf_parm = vsp.FindParm(pd_container, "TurbCfEqnType", "ParasiteDrag")
    if turb_cf_parm:
        vsp.SetParmVal(turb_cf_parm, 7.0)

    # 設置 RefFlag = 0 (使用手動 Sref)
    ref_flag_parm = vsp.FindParm(pd_container, "RefFlag", "ParasiteDrag")
    if ref_flag_parm:
        vsp.SetParmVal(ref_flag_parm, 0.0)

    # 設置 GeomSet = 0 (SET_ALL)
    set_parm = vsp.FindParm(pd_container, "Set", "ParasiteDrag")
    if set_parm:
        vsp.SetParmVal(set_parm, 0.0)

    vsp.Update()
```

### 驗證結果

**修正後的結果：**
- **API CD: 0.020453** ✅
- **GUI CD: 0.02045** ✅
- **差異: 0.01%** ✅✅✅
- **Swet: 3.368035 m²** ✅（完全匹配）

**生成的 CSV（正確）：**
```csv
Mach, Altitude (m), Vinf (m/s), S_ref (m^2)
0.019101, 0.000000, 6.500000, 1.000000

Temp (C), Pressure (lbf/ft^2), Density (kg/m^3)
15.000000, 2116.216195, 1.224978

Lam Cf Eqn, Turb Cf Eqn
Laminar Blasius, Low Reynolds Number Prandtl Power Law

Component Name,S_wet (m^2),L_ref (m),t/c or d/l,FF,FF Eqn Type,Re,% Lam,Cf,Q,f (m^2),Cd,% Total
Final_Fixed_Test,3.368035, 2.500000, 3.808012,1.328623, Hoerner Streamlined Body,1112446.291866, 0.000000,0.004571, 1.000000,0.020453, 0.020453, 100.000000
```

## 關鍵要點

### 1. SetAnalysisInput vs SetParmVal

| 方法 | 用途 | 是否持久化 |
|------|------|------------|
| `vsp.SetAnalysisInput()` | 設置運行時分析參數 | ❌ 不保存到文件 |
| `vsp.SetParmVal()` | 直接修改參數容器中的值 | ✅ 保存到文件 |

### 2. 正確的 API 調用流程

**生成幾何時（在保存文件前）：**
```python
# 1. 找到 ParasiteDragSettings 容器
pd_container = vsp.FindContainer("ParasiteDragSettings", 0)

# 2. 使用 FindParm + SetParmVal 設置每個參數
parm_id = vsp.FindParm(pd_container, "參數名", "ParasiteDrag")
vsp.SetParmVal(parm_id, 值)

# 3. Update 和保存
vsp.Update()
vsp.WriteVSPFile(filepath)
```

**執行分析時（如果文件設置正確）：**
```python
# 簡單調用即可，使用文件中保存的設置
vsp.SetAnalysisInputDefaults("ParasiteDrag")
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Rho", [rho])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Vinf", [velocity])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Mu", [mu])
vsp.ExecAnalysis("ParasiteDrag")
```

### 3. 重要的參數值

| 參數 | 正確值 | 說明 |
|------|--------|------|
| `LengthUnit` | 2.0 | LEN_M (meters) |
| `Sref` | 1.0 | 參考面積 (m²) |
| `Alt` | 0.0 | 海平面高度 (m) |
| `AltLengthUnit` | 1.0 | meters |
| `Vinf` | 6.5 | 速度 (m/s) |
| `VinfUnitType` | 1.0 | m/s |
| `Temp` | 15.0 | 溫度 (°C) |
| `TempUnit` | 1.0 | Celsius |
| `LamCfEqnType` | 0.0 | CF_LAM_BLASIUS |
| `TurbCfEqnType` | 7.0 | CF_TURB_POWER_LAW_PRANDTL_LOW_RE |
| `RefFlag` | 0.0 | 使用手動 Sref |
| `Set` | 0.0 | SET_ALL |

## 常見錯誤

### ❌ 錯誤做法
```python
# 這樣設置不會保存到文件！
vsp.SetAnalysisInputDefaults("ParasiteDrag")
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Sref", [1.0])
vsp.SetIntAnalysisInput("ParasiteDrag", "LengthUnit", [vsp.LEN_M])
vsp.WriteVSPFile(filepath)  # 文件中仍然是預設值！
```

### ✅ 正確做法
```python
# 直接修改參數容器中的值
pd_container = vsp.FindContainer("ParasiteDragSettings", 0)
sref_parm = vsp.FindParm(pd_container, "Sref", "ParasiteDrag")
vsp.SetParmVal(sref_parm, 1.0)  # 這樣才會保存到文件
vsp.Update()
vsp.WriteVSPFile(filepath)  # 正確的值被保存！
```

## 參考資料

1. OpenVSP API 文檔：`docs/VSP_API_Doc.html`
2. 成功的範例：`src/analysis/drag_analysis.py`
3. 論壇討論：OpenVSP Google Groups - "Geom ID not included in Parasite Drag calculation"
4. 修正後的幾何生成器：`src/geometry/cst_geometry_math_driven.py`
5. 測試腳本：`tests/test_final_fix.py`

## 總結

這個問題的關鍵是理解 OpenVSP API 中**運行時參數**和**持久化參數**的區別：

- **運行時參數**（SetAnalysisInput）：僅在當前會話有效
- **持久化參數**（SetParmVal）：保存到 VSP 文件中

要確保 ParasiteDrag 分析使用正確的設置，必須在生成 VSP 文件時，**直接修改 ParasiteDragSettings 容器中的參數值**，而不是僅僅調用 SetAnalysisInput。

修正後，API 和 GUI 的結果完全一致（差異 < 0.01%）！
