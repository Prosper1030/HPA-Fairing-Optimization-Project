# HPA整流罩優化器實現日誌

## 最新更新：2026-01-05

### ✅ 完成：上下邊界獨立反推法（側視圖幾何）

#### 問題背景
- 之前的方法：對稱超橢圓 + Z偏移，無法實現真正的上下非對稱
- Gemini建議：改用「上下邊界獨立反推法」

#### 新的幾何定義

**座標系：**
- XZ平面：側視圖
- 原點(0,0)：機頭最尖端
- X軸向後，Z軸向上

**幾何要求：**
1. 機頭：上下邊界都從(0,0)出發，指向正前方（上下對稱於X軸）
2. 上邊界：向上拱起至H_top_max，然後收束到機尾
3. 下邊界：向下包覆至-H_bot_max，然後平順上升到機尾
4. 機尾：上下邊界在(L, Tail_Rise)完美交會成尖點

**數學實現：混合法**

```python
# 1. 生成基礎CST曲線
z_upper_cst = CST_Modeler.cst_curve(psi, H_top_max, N1, N2_top, weights)
z_lower_cst = -CST_Modeler.cst_curve(psi, H_bot_max, N1, N2_bot, weights)

# 2. 混合因子（在機尾附近才混合到Tail_Rise）
blend_start = 0.75  # 從75%位置開始混合
blend_factor = 0 for psi < blend_start
blend_factor = ((psi - blend_start) / (1 - blend_start))^2 for psi >= blend_start

# 3. 混合到目標高度
z_upper = z_upper_cst * (1 - blend_factor) + Tail_Rise * blend_factor
z_lower = z_lower_cst * (1 - blend_factor) + Tail_Rise * blend_factor

# 4. 反推VSP參數
Super_Height = z_upper - z_lower  # 總厚度
Z_Loc = (z_upper + z_lower) / 2   # 幾何中心
```

**驗證結果：**
- ✅ 上邊界最大值：0.954 m（期望 0.95 m，誤差 0.4%）
- ✅ 下邊界最小值：-0.350 m（期望 -0.35 m，完美）
- ✅ 機頭閉合：間隙 0.000 m
- ✅ 機尾閉合：間隙 0.000 m
- ✅ 機頭對稱：上下使用相同N1=0.5

#### GA參數化能力

**可調整的基因（9個）：**
1. `L`：總長度 [1.8 - 3.0 m]
2. `W_max`：最大全寬 [0.48 - 0.65 m]
3. `H_top_max`：上半部高度 [0.85 - 1.15 m]
4. `H_bot_max`：下半部高度 [0.25 - 0.50 m]
5. `N1`：機頭鈍度 [0.3 - 0.7]（上下共用）
6. `N2_top`：上曲線形狀 [0.5 - 1.0]
7. `N2_bot`：下曲線形狀 [0.5 - 1.0]
8. `X_max_pos`：最大值位置 [0.2 - 0.4]（預留）
9. `X_offset`：收縮開始位置 [0.6 - 0.8]（預留）

**固定參數（可選擇性調整）：**
- `weights = [0.25, 0.35, 0.30, 0.10]`：CST權重
- `blend_start = 0.75`：機尾混合開始位置
- `blend_power = 2.0`：混合曲線冪次
- `Tail_Rise = 0.10 m`：機尾上升高度（可改為基因）

#### 下一步：應用到VSP

**需要實現：**
1. ✅ 側視圖曲線生成（已完成）
2. ⏳ 修改`create_fuselage()`使用新方法
3. ⏳ 調整Skinning切線角度（上下分開計算）
4. ⏳ 使用`ZLocPercent`設置截面Z位置
5. ⏳ 測試完整模型生成

**Skinning要求：**
- 上曲線切線：使用N2_top
- 下曲線切線：使用N2_bot
- 左右對稱：可共用

---

## 歷史記錄

### 2026-01-04：Z偏移方案（已廢棄）
- 使用對稱超橢圓 + Z偏移
- 問題：無法實現真正的上下非對稱
- 問題：Skinning切線角度未分離

### 2026-01-03：CST峰值歸一化
- 實現峰值歸一化方法
- 驗證尺寸精度：寬度誤差0.15%，高度誤差0.14%

### 2026-01-02：初始實現
- 基本CST曲線實現
- VSP API整合
- ParasiteDrag API修復
