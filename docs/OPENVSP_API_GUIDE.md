# **OPENVSP_API_GUIDE**

這份文件是給 AI 看的「語法參考書」，確保它寫出來的 code 能跑。

---

# OpenVSP Python API (v3.42.3) 實戰指南與注意事項

## 1. 版本關鍵限制 (CRITICAL)
此環境使用的 OpenVSP API 版本為 `3.42.3` (Windows Embedded Python)。
* **已知問題**：部分高階封裝函數（如 `vsp.FindAnalysis()`, `vsp.ComputeGeom()`）在此版本中無法使用或會拋出 `AttributeError`。
* **解決方案**：所有分析操作必須透過 **「字串呼叫 (String-based Access)」** 與 **「CSV 檔案讀取」** 來完成。

## 2. 幾何建模 (Geometry Modeling)

### 2.1 建立機身與切割截面
避免使用 `while` 迴圈檢查截面數量（容易死結），應使用定量切割。

```python
# 標準起手式
vsp.ClearVSPModel()
fuse_id = vsp.AddGeom("FUSELAGE")
vsp.SetParmVal(fuse_id, "Length", "Design", length_val)

# 切割截面 (Cut Cross Sections)
# 警告：不要切 Index 0 (Point)，容易導致 VSP 幾何錯誤。建議切 Index 1。
target_sections = 40
xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
current = vsp.GetNumXSec(xsec_surf)
needed = target_sections - current

for _ in range(needed):
    vsp.CutXSec(fuse_id, 1)  # Always cut at index 1

vsp.Update()  # Force update after all cuts
```

### 2.2 截面形狀控制 (Point vs. Super Ellipse)

⚠️ **重要修正**：此版本必須使用 `ChangeXSecShape()` 而非 `SetXSecShape()`

CST 生成的機身必須正確設定截面類型，否則體積會是 0。

```python
xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
num_secs = vsp.GetNumXSec(xsec_surf)

for i in range(num_secs):
    psi = i / (num_secs - 1)  # 無因次位置 (0~1)

    # 判斷頭尾
    is_tip = (i == 0) or (i == num_secs - 1)

    if is_tip:
        # ✅ 正確：頭尾必須是 Point
        vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_POINT)
    else:
        # ✅ 正確：中段設為 Super Ellipse
        vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_SUPER_ELLIPSE)

    # 取得截面物件來設定參數
    xsec = vsp.GetXSec(xsec_surf, i)

    # 設定位置 (0.0 ~ 1.0)
    vsp.SetParmVal(vsp.GetXSecParm(xsec, "XLocPercent"), psi)

    if not is_tip:
        # 設定幾何尺寸 (CST 計算結果)
        # 注意：這裡的參數名稱是 Super_Width/Super_Height（物理尺寸）
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Width"), calculated_width)
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Height"), calculated_height)

        # 設定超橢圓指數 (控制形狀)
        # Super_M 和 Super_N 是形狀係數，不是尺寸
        # m = n = 2.0: 標準橢圓
        # m = n = 2.5: 稍微方形（推薦，容納肩膀）
        # m = n = 3.0: 更方形
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_M"), 2.5)
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_N"), 2.5)

vsp.Update()  # 必須在所有設定完成後更新
```

### 2.3 可用的截面類型常數

```python
vsp.XS_POINT              # 0: 點（用於頭尾）
vsp.XS_CIRCLE             # 1: 圓形
vsp.XS_ELLIPSE            # 標準橢圓（已廢棄，用 XS_SUPER_ELLIPSE）
vsp.XS_SUPER_ELLIPSE      # 超橢圓（推薦使用）
vsp.XS_ROUNDED_RECTANGLE  # 圓角矩形
vsp.XS_GENERAL_FUSE       # 通用機身
# ... 還有其他翼型用的類型
```

## 3. 空氣動力分析 (Parasite Drag Analysis)

### 3.1 執行分析 (String-based)

不能使用物件導向的 Analysis ID，必須用字串。

```python
analysis_name = "ParasiteDrag"

# 設定預設值
vsp.SetAnalysisInputDefaults(analysis_name)

# 設定流體參數
# ⚠️ 注意：參數名稱是 "Vinf" 不是 "V_inf"
vsp.SetDoubleAnalysisInput(analysis_name, "Rho", [1.1839])      # kg/m³
vsp.SetDoubleAnalysisInput(analysis_name, "Vinf", [6.5])        # m/s
vsp.SetDoubleAnalysisInput(analysis_name, "Mu", [1.8371e-05])   # kg/(m·s)

# 執行分析（會自動生成 CSV 檔案）
vsp.ExecAnalysis(analysis_name)
```

### 3.2 讀取結果 (CSV Parser)

`vsp.GetDoubleAnalysisData()` 可能會抓不到數據，最穩健的方法是讀取自動生成的 CSV。

**目標檔案**：`{GeomName}_ParasiteBuildUp.csv`

**目標欄位**：
- `f (ft^2)` 或 `f`: 即 **Equivalent Flat Plate Area** ($C_d \cdot A$)。這是優化的主要指標。
- `S_wet (ft^2)`: 濕面積 (Wetted Area)
- `Cd`: 阻力係數

**計算公式**：
$$\text{Drag (N)} = q \times f$$

其中動壓 $q = 0.5 \cdot \rho \cdot V^2$

**CSV 解析範例**：

```python
import csv

def parse_parasite_drag_csv(csv_filepath, velocity, rho):
    """解析 ParasiteBuildUp CSV 獲取阻力數據"""
    q = 0.5 * rho * (velocity ** 2)

    with open(csv_filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = list(reader)

        # 尋找標題列
        for i, row in enumerate(rows):
            if "Component Name" in row[0]:
                header_idx = i
                # 找出欄位索引
                f_idx = next(j for j, col in enumerate(row) if "f (" in col.lower())
                swet_idx = next(j for j, col in enumerate(row) if "s_wet" in col.lower())
                cd_idx = next(j for j, col in enumerate(row) if col.lower().strip() == "cd")
                break

        # 尋找 "Totals:" 列
        for row in rows[header_idx+1:]:
            if "total" in row[0].lower():
                f_val = float(row[f_idx])
                s_wet = float(row[swet_idx])
                cd = float(row[cd_idx])

                drag = q * f_val
                return {"Drag": drag, "CdA": f_val, "Swet": s_wet, "Cd": cd}

    return None
```

## 4. 常見錯誤與除錯 (Common Errors & Debugging)

### 4.1 幾何體積為 0
**症狀**：生成的機身在 OpenVSP 中顯示為線或點
**原因**：
- 截面類型設定錯誤（全部都是 Point）
- 忘記呼叫 `vsp.Update()`
- CST 計算的半徑為負數或 0

**解決方案**：
1. 確保中段截面使用 `vsp.XS_SUPER_ELLIPSE`
2. 在所有參數設定完成後呼叫 `vsp.Update()`
3. 在設定尺寸時加上防呆：`max(calculated_value, 0.001)`

### 4.2 分析執行後找不到 CSV
**症狀**：`ExecAnalysis()` 執行無錯誤，但找不到輸出檔案
**原因**：
- 幾何名稱與檔名不符
- CSV 生成在錯誤的工作目錄
- 幾何體積為 0 導致分析失敗（無聲錯誤）

**解決方案**：
1. 使用 `vsp.GetGeomName(geom_id)` 確認名稱
2. 先用 `vsp.WriteVSPFile()` 存檔，再用 `vsp.ReadVSPFile()` 載入後分析
3. 檢查幾何是否有效：在 OpenVSP GUI 中打開 .vsp3 檔案目視檢查

### 4.3 超橢圓參數設定無效
**症狀**：設定了 Super_M/Super_N，但截面仍是標準橢圓
**原因**：在呼叫 `ChangeXSecShape()` 之前設定參數

**解決方案**：
```python
# ❌ 錯誤順序
xsec = vsp.GetXSec(xsec_surf, i)
vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_M"), 2.5)
vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_SUPER_ELLIPSE)  # 會覆蓋之前的設定

# ✅ 正確順序
vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_SUPER_ELLIPSE)
xsec = vsp.GetXSec(xsec_surf, i)
vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_M"), 2.5)
```

## 5. 效能優化建議

### 5.1 減少不必要的 Update()
- 不要在迴圈內每次都呼叫 `vsp.Update()`
- 在所有截面設定完成後統一呼叫一次

### 5.2 批次處理
- 使用多執行緒時，每個執行緒應該使用獨立的工作目錄
- OpenVSP API 不是 thread-safe，需要用 Process Pool 而非 Thread Pool

### 5.3 檔案管理
- 分析後立即移動 CSV 檔案到輸出資料夾
- 使用時間戳或流水號避免檔名衝突

---

## 附錄：完整工作流程範例

```python
import openvsp as vsp
import os

# 1. 建立幾何
vsp.ClearVSPModel()
fuse_id = vsp.AddGeom("FUSELAGE")
vsp.SetGeomName(fuse_id, "Test_Fairing")
vsp.SetParmVal(fuse_id, "Length", "Design", 2.5)

# 2. 切割並設定截面
xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
for _ in range(38):  # 需要 40 個截面，預設有 2 個
    vsp.CutXSec(fuse_id, 1)

num_secs = vsp.GetNumXSec(xsec_surf)
for i in range(num_secs):
    is_tip = (i == 0) or (i == num_secs - 1)
    if is_tip:
        vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_POINT)
    else:
        vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_SUPER_ELLIPSE)
        xsec = vsp.GetXSec(xsec_surf, i)
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "XLocPercent"), i/(num_secs-1))
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Width"), 0.4)
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Height"), 0.3)
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_M"), 2.5)
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_N"), 2.5)

vsp.Update()

# 3. 存檔
vsp.WriteVSPFile("Test_Fairing.vsp3")

# 4. 執行分析
vsp.ClearVSPModel()
vsp.ReadVSPFile("Test_Fairing.vsp3")
vsp.SetAnalysisInputDefaults("ParasiteDrag")
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Vinf", [6.5])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Rho", [1.1839])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Mu", [1.8371e-05])
vsp.ExecAnalysis("ParasiteDrag")

# 5. 讀取結果
csv_file = "Test_Fairing_ParasiteBuildUp.csv"
if os.path.exists(csv_file):
    print(f"✅ 分析完成，結果位於 {csv_file}")
else:
    print("❌ 分析失敗，未找到 CSV 檔案")
```

---

**最後更新**：2025-01-03
**測試環境**：OpenVSP 3.42.3, Python 3.11.0
**已驗證功能**：✅ CST 幾何生成、✅ 超橢圓截面、✅ Parasite Drag 分析
