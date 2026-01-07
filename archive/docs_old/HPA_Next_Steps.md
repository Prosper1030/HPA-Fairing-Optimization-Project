# HPA 優化器 - 下一步行動計劃

**時間**: 2026-01-04 21:45
**狀態**: 核心問題已識別，制定解決方案

---

## 當前狀況總結

### ✅ 已確認正常
1. 餘弦分布 - 完全正確
2. 切線角度 - 完全正確

### ❌ 核心問題
1. **CST 曲線形狀不正確**
   - 診斷結果：在目標位置 (psi=0.25) 數值正確
   - 但全局最大值出現在錯誤位置 (psi=0.36)
   - 說明 ScaleFactor 方法有問題

2. **完全沒有實現上下非對稱**
   - 當前：用平均高度 `(H_top + H_bot) / 2`
   - 用戶需求：**上下兩條獨立的 CST 曲線**
   - VSP Super_Ellipse 無法支持上下不同高度

---

## 診斷數據

### CST 計算測試結果：

```
在目標位置 psi=0.25 處:
  寬度: 0.6000 m ✓ (正確)
  上高: 0.9500 m ✓ (正確)
  下高: 0.3500 m ✓ (正確)

全局最大值位置:
  寬度: 0.6454 m 在 psi=0.361 ❌
  上高: 1.0318 m 在 psi=0.400 ❌

VSP 截圖顯示 (截面17):
  Width: 0.644 m
  Height: 0.702 m
```

**結論**: 我的 CST 計算雖然在指定位置正確，但整體曲線形狀錯誤。

---

## 根本問題分析

### 問題 1: CST 方法錯誤

我使用的方法：
```python
# 錯誤的方法：ScaleFactor 強制在 x_max_pos 達到 max_value
eta = max_value * scale_factor * C * S
```

正確的方法（從 cst_geometry_math_driven.py）：
```python
# 正確：weights 本身就包含尺度信息
r = C * S * length  # length 是總長度
diameter = r * 2
```

**差異**:
- 原始方法：weights 陣列本身攜帶尺度信息
- 我的方法：強制 ScaleFactor，破壞了原始曲線形狀

### 問題 2: 上下非對稱無法實現

VSP Super_Ellipse 參數：
- `Super_Width` - 寬度（直徑）
- `Super_Height` - 高度（直徑）
- **只有一個 Height 值！**

無法直接設置：
- ❌ Top Height = 0.95 m
- ❌ Bottom Height = 0.35 m

---

## 解決方案

### 方案 A: 修正 CST 計算 + 使用 File XSec ⭐ 推薦

**步驟 1: 修正 CST 計算**
- 放棄 ScaleFactor 方法
- 使用與 `cst_geometry_math_driven.py` 相同的邏輯
- Weights 需要重新標定以包含尺度信息

**步驟 2: 實現上下兩條 CST 曲線**
- 生成上曲線：`top_curve(psi)` 使用 `N2_top`, `H_top_max`
- 生成下曲線：`bottom_curve(psi)` 使用 `N2_bot`, `H_bot_max`
- 合併為完整輪廓

**步驟 3: 使用 VSP File XSec**
```python
# 1. 生成截面輪廓點
def generate_xsec_profile(gene, psi):
    # 上半部
    theta_top = np.linspace(0, pi, 50)  # 從右到左
    r_top = top_curve(psi)
    x_top = r_top * cos(theta_top)
    y_top = r_top * sin(theta_top)

    # 下半部
    theta_bot = np.linspace(pi, 2*pi, 50)  # 從左到右
    r_bot = bottom_curve(psi)
    x_bot = r_bot * cos(theta_bot)
    y_bot = r_bot * sin(theta_bot)

    # 合併
    return combine(x_top, y_top, x_bot, y_bot)

# 2. 保存為 VSP File XSec 格式
def save_xsec_file(profile, filename):
    # VSP XSec 格式研究中...
    pass

# 3. 在 VSP 中使用
vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_FILE_FUSE)
# 設置檔案路徑...
```

### 方案 B: 完全重寫 - 參考原始代碼

**直接複製 `cst_geometry_math_driven.py` 的邏輯**：
```python
# 使用相同的 weights 概念
W_w = [...]  # 寬度 weights
H_top_w = [...]  # 上部高度 weights (需要重新標定)
H_bot_w = [...]  # 下部高度 weights (需要重新標定)

r_width = CSTDerivatives.cst_radius(psi, N1, N2_avg, W_w, L)
r_top = CSTDerivatives.cst_radius(psi, N1, N2_top, H_top_w, L)
r_bot = CSTDerivatives.cst_radius(psi, N1, N2_bot, H_bot_w, L)

# 然後用 File XSec...
```

---

## 立即需要研究的問題

### 1. VSP File XSec 格式 🔥 最重要

**需要找到答案**:
- File XSec 的檔案格式是什麼？
- 如何定義截面輪廓點？
- 座標系統是什麼？(XY? 相對/絕對?)
- 如何在 Python API 中設置？

**可能的資料來源**:
- `docs/VSP_API_Doc.html`
- VSP 範例檔案（是否有 File XSec 範例？）
- OpenVSP GitHub 範例
- OpenVSP 論壇

### 2. CST Weights 的正確尺度

**需要理解**:
- 原始代碼中 `weights = [0.25, 0.35, 0.30, 0.10]` 的含義
- 如何從用戶參數 `H_top_max = 0.95` 轉換為 weights
- 是否需要重新標定 weights

### 3. 截面輪廓生成邏輯

**需要設計**:
- 如何從兩條 CST 曲線（上/下）生成閉合輪廓？
- 寬度曲線如何與高度曲線配合？
- 是否需要插值？

---

## 建議的行動順序

### 第一優先：研究 File XSec

1. [ ] 查閱 VSP API 文檔中的 File XSec 章節
2. [ ] 搜尋 VSP 範例檔案中是否有 File XSec 使用案例
3. [ ] 在 OpenVSP GUI 中手動創建一個 File XSec 測試
4. [ ] 查看生成的檔案格式
5. [ ] 編寫 Python 程式碼生成相同格式

### 第二優先：修正 CST 計算

1. [ ] 完全理解原始 `cst_radius` 的邏輯
2. [ ] 理解 weights 的尺度含義
3. [ ] 設計從用戶參數到 weights 的轉換方法
4. [ ] 測試 CST 曲線是否正確

### 第三優先：整合測試

1. [ ] 生成上下兩條 CST 曲線
2. [ ] 合併為截面輪廓
3. [ ] 保存為 File XSec
4. [ ] 在 VSP 中驗證
5. [ ] 檢查阻力計算結果

---

## 時間估計

- **研究 File XSec**: 1-2 小時
- **修正 CST 計算**: 1 小時
- **實現輪廓生成**: 1 小時
- **整合測試**: 1 小時
- **總計**: 4-6 小時

---

## 用戶決策點

請用戶決定：

1. **是否需要我先研究 File XSec？**
   - 如果是：我將查閱文檔並提供詳細報告
   - 如果否：可以先嘗試其他方法（但可能無法實現上下非對稱）

2. **是否接受暫時使用對稱版本？**
   - 先修正 CST 尺寸問題
   - 使用平均高度
   - 確保數值正確後再處理非對稱

3. **優先級如何排序？**
   - A: 上下非對稱最重要（需要 File XSec）
   - B: 先確保尺寸正確，再處理非對稱

---

**創建時間**: 2026-01-04 21:45
**狀態**: 等待用戶決策
