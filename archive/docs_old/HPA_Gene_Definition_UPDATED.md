# HPA 整流罩優化器 - 基因參數定義 (更新版)

**日期**: 2026-01-04 21:50
**狀態**: 已明確半徑 vs 直徑定義

---

## 基因參數定義（9個變數）

### **明確說明：半徑 vs 直徑**

為了避免混淆，以下參數明確標示其含義：

| 參數 | 範圍 (m) | 物理意義 | CST 計算注意事項 |
|------|----------|----------|------------------|
| `L` | (1.8, 3.0) | 整流罩總長 | 用於 psi 計算 |
| **`W_max`** | (0.48, 0.65) | **最大全寬 (Full Width)** | ⚠️ **代入 CST 計算 Y 座標時，請務必除以 2** |
| **`H_top_max`** | (0.85, 1.15) | **上半部高度 (Upper Radius)**，從 Z=0 往上 | 已經是半徑，直接用於 CST |
| **`H_bot_max`** | (0.25, 0.50) | **下半部高度 (Lower Radius)**，從 Z=0 往下 | 已經是半徑，直接用於 CST |
| `N1` | (0.4, 0.9) | 機頭形狀係數 | CST 類別函數 |
| `N2_top` | (0.5, 1.0) | 上機尾形狀係數 | 上部 CST |
| `N2_bot` | (0.5, 1.0) | 下機尾形狀係數 | 下部 CST |
| `X_max_pos` | (0.2, 0.5) | 最大截面位置 (0-1) | psi 值 |
| `X_offset` | (0.5, 1.0) | 踏板位置 (m) | 絕對距離 |

---

## 詳細說明

### `W_max` - 最大全寬 (Full Width)

- **定義**: 從左側最外緣到右側最外緣的**全寬度**（直徑）
- **CST 計算時**：
  ```python
  # 錯誤做法：
  y_coord = CST_curve(psi, W_max, ...)  # ❌ 會太寬

  # 正確做法：
  y_half_width = CST_curve(psi, W_max / 2, ...)  # ✅ 用半徑
  y_coord = y_half_width  # 然後對稱到左右
  ```

### `H_top_max` - 上半部高度 (Upper Radius)

- **定義**: 從**中心線 Z=0** 到**頂部**的距離（半徑）
- **物理意義**: 駕駛員上方的空間需求
- **CST 計算時**: 直接使用
  ```python
  z_top = CST_curve(psi, H_top_max, N1, N2_top, ...)  # ✅ 已經是半徑
  ```

### `H_bot_max` - 下半部高度 (Lower Radius)

- **定義**: 從**中心線 Z=0** 到**底部**的距離（半徑）
- **物理意義**: 駕駛員下方的空間需求（斜躺姿勢，下方較小）
- **CST 計算時**: 直接使用
  ```python
  z_bot = -CST_curve(psi, H_bot_max, N1, N2_bot, ...)  # ✅ 已經是半徑，負號表示向下
  ```

---

## 座標系統

```
        ↑ Z (上)
        |
        |   H_top_max (上半部半徑)
    ----+----→ Y (橫向)
        |   H_bot_max (下半部半徑)
        |
        ↓

    ←------- W_max (全寬) -------→
    ←-- W_max/2 --→ 中心 ←-- W_max/2 --→
```

---

## 截面輪廓生成邏輯

### 在每個截面位置 `psi`：

1. **計算半寬度**（Y 方向）：
   ```python
   y_half = CST_curve(psi, W_max / 2, N1, (N2_top + N2_bot) / 2, ...)
   ```

2. **計算上部高度**（Z 正向）：
   ```python
   z_top = CST_curve(psi, H_top_max, N1, N2_top, ...)
   ```

3. **計算下部高度**（Z 負向）：
   ```python
   z_bot = -CST_curve(psi, H_bot_max, N1, N2_bot, ...)
   ```

4. **生成閉合輪廓點**（逆時針）：
   ```python
   # 右上象限 (0° to 90°)
   for theta in [0, pi/2]:
       x_local = 0
       y = y_half * cos(theta)
       z = z_top * sin(theta)

   # 左上象限 (90° to 180°)
   for theta in [pi/2, pi]:
       y = y_half * cos(theta)
       z = z_top * sin(theta)

   # 左下象限 (180° to 270°)
   for theta in [pi, 3*pi/2]:
       y = y_half * cos(theta)
       z = z_bot * sin(theta - pi)  # 注意：下部用不同高度

   # 右下象限 (270° to 360°)
   for theta in [3*pi/2, 2*pi]:
       y = y_half * cos(theta)
       z = z_bot * sin(theta - pi)
   ```

---

## 硬限制（維持不變）

1. **車架包覆**: `X_offset - 0.3 >= 0`
2. **踏板寬度**: `w(X_offset) >= 0.45 m`
3. **肩膀寬度**: `w(X_offset + 0.5) >= 0.52 m`
4. **肩膀上高**: `h_top(X_offset + 0.5) >= 0.75 m`
5. **肩膀下高**: `h_bot(X_offset + 0.5) >= 0.25 m`
6. **機尾長度**: `L - X_offset >= 1.5 m`

---

## 範例計算

### 測試基因：
```python
{
    'L': 2.5,
    'W_max': 0.60,        # 全寬 60 cm
    'H_top_max': 0.95,    # 上部半徑 95 cm
    'H_bot_max': 0.35,    # 下部半徑 35 cm
    'N1': 0.5,
    'N2_top': 0.7,
    'N2_bot': 0.8,
    'X_max_pos': 0.25,
    'X_offset': 0.7,
}
```

### 在 psi = 0.25 處：

**寬度計算**：
```python
y_half = CST_curve(0.25, 0.60 / 2, 0.5, 0.75, weights, 0.25)
       = CST_curve(0.25, 0.30, ...)  # ✅ 用半徑 30 cm
       ≈ 0.30 m  (在最大位置)
# 全寬 = 0.30 * 2 = 0.60 m ✅
```

**高度計算**：
```python
z_top = CST_curve(0.25, 0.95, 0.5, 0.7, weights, 0.25)
      ≈ 0.95 m  (在最大位置)

z_bot = -CST_curve(0.25, 0.35, 0.5, 0.8, weights, 0.25)
      ≈ -0.35 m  (在最大位置)

# 總高度 = 0.95 + 0.35 = 1.30 m ✅
```

---

## 重要提醒

### ✅ 正確做法

```python
# 寬度：使用半寬度
half_width = gene['W_max'] / 2  # 除以 2
y_radius = CST_curve(psi, half_width, ...)

# 高度：直接使用
z_top = CST_curve(psi, gene['H_top_max'], ...)  # 已經是半徑
z_bot = -CST_curve(psi, gene['H_bot_max'], ...)  # 已經是半徑
```

### ❌ 錯誤做法

```python
# 寬度：不要直接用全寬
y = CST_curve(psi, gene['W_max'], ...)  # ❌ 錯誤！會太寬

# 高度：不要再除以 2
z_top = CST_curve(psi, gene['H_top_max'] / 2, ...)  # ❌ 錯誤！會太矮
```

---

**更新時間**: 2026-01-04 21:50
**狀態**: 參數定義已明確，準備實作
