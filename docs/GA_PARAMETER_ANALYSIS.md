# GA 參數擴展分析報告

**日期：2026-01-07**

---

## 一、參數擴展可行性分析

### 1. 超橢圓 M 和 N 參數

**現況**（`hpa_asymmetric_optimizer.py:540-541`）：
```python
vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_M"), 2.5)
vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_N"), 2.5)
```

**問題**：VSP 的 SuperEllipse 截面只有一對 M 和 N，**不能上下分開**。

**解決方案**：
- **方案A**（簡單）：使用同一對 M 和 N 作為基因，上下相同
- **方案B**（複雜）：使用 File XSec（.fxs 檔案）實現真正的上下不同
  - 代碼中已有 `generate_super_ellipse_profile()` 和 `write_fxs_file()` 函數
  - 需要修改 `VSPModelGenerator.create_fuselage()` 使用 .fxs 方式

**建議**：先用方案A測試，確認效果後再考慮方案B

**建議範圍**：
- `Super_M`: [2.0 - 4.0]（2.0=橢圓，2.5=默認，>2.5=方形化）
- `Super_N`: [2.0 - 4.0]

---

### 2. CST 權重 (weights)

**現況**（`hpa_asymmetric_optimizer.py:185`）：
```python
weights = np.array([0.25, 0.35, 0.30, 0.10])
```

**說明**：
- 4個權重控制 Bernstein 多項式的係數
- 權重決定曲線形狀的分布
- **不需要**加起來等於1（因為會做峰值歸一化）

**可調整性**：✅ 可以作為基因參數

**建議範圍**：
- `w0`: [0.15 - 0.35]（前段斜率）
- `w1`: [0.25 - 0.45]（最大值附近）
- `w2`: [0.20 - 0.40]（後段平滑）
- `w3`: [0.05 - 0.20]（尾部收斂）

**注意**：權重變化會影響曲線形狀，需要仔細測試以確保不會產生異常形狀

---

### 3. Z 參數（非對稱性相關）

**現況**（`hpa_asymmetric_optimizer.py:203-208`）：
```python
tail_rise = 0.10   # m，機尾上升高度
blend_start = 0.75 # 從75%位置開始混合
blend_power = 2.0  # 混合曲線的冪次
```

**說明**：
- `tail_rise`：決定尾部收斂的高度位置
- `blend_start`：決定從哪裡開始將曲線混合到尾部
- `blend_power`：控制混合的平滑程度（越大越突然）

**可調整性**：✅ 可以作為基因參數

**會不會影響連續性？**
- **不會**，因為代碼中有單調收斂處理（第236-286行）
- 只要在合理範圍內，模型會自動確保平滑

**建議範圍**：
- `tail_rise`: [0.05 - 0.20] m
- `blend_start`: [0.65 - 0.85]
- `blend_power`: [1.5 - 3.0]

---

## 二、現有約束條件

**位置**：`hpa_asymmetric_optimizer.py:398-472` (`ConstraintChecker` 類)

### 目前的硬約束：

| 約束名稱 | 常數值 | 檢查方式 |
|----------|--------|----------|
| 車架包覆 | 0.3 m | x_frame >= 0 |
| 踏板寬度 | 0.45 m | w_pedal >= 0.45 |
| 肩膀寬度 | 0.52 m | w_shoulder >= 0.52 |
| 肩膀上高 | 0.75 m | h_top_shoulder >= 0.75 |
| 肩膀下高 | 0.25 m | h_bot_shoulder >= 0.25 |
| 機尾長度 | 1.5 m | tail_length >= 1.5 |

### 是否需要額外約束？

**現有範圍限制**（在基因定義中）：
- ✅ 已有幾何參數範圍限制
- ✅ 已有CST參數範圍限制

**需要生成後才能判斷的**：
- ✅ 座艙空間（通過 ConstraintChecker）
- ⚠️ **曲面連續性**：目前沒有明確檢查，但代碼設計確保了連續性
- ⚠️ **濕面積合理性**：可以添加檢查（例如 Swet > 3.0 m²）

---

## 三、評分公式

**目前的適應度函數**（`hpa_asymmetric_optimizer.py:693`）：
```python
# fitness (越小越好，阻力 N)
return drag  # 或者約束違反時返回 1e6
```

**問題**：沒有找到帶 k 的評分公式

**建議的評分公式**：
```python
def fitness(gene, result, constraints_result):
    """
    適應度 = CdA + k1 * 約束違反懲罰 + k2 * 濕面積懲罰

    k1: 約束違反懲罰係數（建議 1000）
    k2: 濕面積懲罰係數（建議 0.01）
    """
    if result is None:
        return float('inf')

    cda = result['CdA']

    # 約束違反懲罰
    penalty = 0
    for name, check in constraints_result.items():
        if not check['pass']:
            violation = check['required'] - check['value']
            penalty += k1 * max(0, violation)

    # 濕面積懲罰（鼓勵更小的表面積）
    swet_penalty = k2 * result['Swet']

    return cda + penalty + swet_penalty
```

---

## 四、擴展後的完整基因定義

```python
gene = {
    # === 幾何參數（4個）===
    'L': 2.5,              # 整流罩總長 [1.8 - 3.0 m]
    'W_max': 0.60,         # 最大全寬 [0.48 - 0.65 m]
    'H_top_max': 0.95,     # 上半部高度 [0.85 - 1.15 m]
    'H_bot_max': 0.35,     # 下半部高度 [0.25 - 0.50 m]

    # === CST形狀參數（3個）===
    'N1': 0.5,             # Class function N1 [0.3 - 0.7]
    'N2_top': 0.7,         # Shape function N2（上）[0.5 - 1.0]
    'N2_bot': 0.8,         # Shape function N2（下）[0.5 - 1.0]

    # === 位置參數（2個）===
    'X_max_pos': 0.25,     # 最大寬度/高度位置 [0.2 - 0.4]
    'X_offset': 0.7,       # 收縮開始位置 [0.6 - 0.8]

    # === 新增：超橢圓參數（2個）===
    'Super_M': 2.5,        # 超橢圓指數M [2.0 - 4.0]
    'Super_N': 2.5,        # 超橢圓指數N [2.0 - 4.0]

    # === 新增：尾部參數（3個）===
    'tail_rise': 0.10,     # 機尾上升高度 [0.05 - 0.20 m]
    'blend_start': 0.75,   # 混合開始位置 [0.65 - 0.85]
    'blend_power': 2.0,    # 混合曲線冪次 [1.5 - 3.0]

    # === 新增：CST權重（4個，可選）===
    'w0': 0.25,            # 前段斜率 [0.15 - 0.35]
    'w1': 0.35,            # 最大值附近 [0.25 - 0.45]
    'w2': 0.30,            # 後段平滑 [0.20 - 0.40]
    'w3': 0.10,            # 尾部收斂 [0.05 - 0.20]
}
```

**總計**：9 → 18 個基因變數（可選擇性啟用）

---

## 五、待確認問題

1. **帶 k 的評分公式**：找不到記錄，請確認是否有特定公式
2. **CST 權重是否要納入 GA**：權重變化對形狀影響較大，建議先測試
3. **Super_M/N 是否要上下分開**：需要決定是否使用 .fxs 方式

---

## 六、下一步

1. 生成測試檔案驗證新參數的可行性
2. 確認評分公式
3. 建立流體條件 JSON
4. 實現 GA 工作流
