# HPA 優化器問題分析與修正

**日期**: 2026-01-04 21:30
**狀態**: 發現關鍵問題，制定修正方案

---

## 用戶反饋的問題

### ✅ 正常部分
1. 餘弦分布 - 正確 ✓
2. 切線角度 - 正確 ✓

### ❌ 問題部分
1. **尺寸完全不對** - 模型太細長
2. **沒有上下非對稱** - 完全對稱
3. **需要實現上下兩條 CST 曲線**

---

## 問題分析

### 問題 1: 尺寸錯誤

**症狀**（從 VSP GUI 截圖）:
- 截面17: Width = 0.644 m, Height = 0.702 m
- 但期望: Width ≈ 0.60 m, Height ≈ 0.65 m
- 視覺上模型太細

**根本原因**:
在 `cst_geometry_math_driven.py` 中:
```python
r_width = CSTDerivatives.cst_radius(psi, N1, N2, W_w, L)  # 返回半徑
w = max(r_width * 2, 0.001)  # 半徑 * 2 = 直徑 ✓
vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Width"), w)
```

在我的 `hpa_asymmetric_optimizer.py` 中:
```python
width = CST_Modeler.cst_curve(...)  # 返回什麼？
vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Width"), width)  # 沒有 *2 ❌
```

**問題**:
1. `CST_Modeler.cst_curve()` 可能返回的是半徑，但沒有乘以2
2. 或者 `cst_curve` 的 ScaleFactor 計算有誤
3. 需要確認 CST 計算邏輯

### 問題 2: 上下非對稱未實現

**當前實現**:
```python
height_avg = (height_top + height_bot) / 2.0  # 用平均值
vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Height"), height_avg)  # 單一高度
```

**問題**:
- VSP Super_Ellipse 只有一個 `Super_Height` 參數
- 無法直接設置上下不同的高度值
- 用戶要求：**上下兩條 CST 曲線**

**可能的解決方案**:

#### 方案 A: 使用 File XSec 導入自定義截面 ⭐推薦
```python
# 1. 根據上下兩條 CST 曲線生成截面輪廓點
# 2. 保存為 VSP XSec 格式檔案
# 3. 使用 vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_FILE_FUSE)
# 4. 導入自定義截面
```

**優點**:
- 完全控制上下形狀
- 真正實現兩條 CST 曲線

**缺點**:
- 需要生成 XSec 檔案
- 較複雜

#### 方案 B: 使用 Z 偏移（如果 VSP 支持）
```python
# 設置截面的 Z 位置偏移
# 需要確認 VSP API 是否有此功能
```

#### 方案 C: Stack 組合（複雜）
- 生成上半部 Fuselage
- 生成下半部 Fuselage
- 使用 Stack 組合

**缺點**: 架構改動大

#### 方案 D: 使用 Super_Ellipse 的 TopLRad/BotLRad（需確認）
- 檢查 VSP 是否支持上下不同半徑的 Super_Ellipse

---

## 修正計劃

### 第一步：修正 CST 尺寸計算

**目標**: 確保寬度和高度數值正確

**行動**:
1. ✅ 檢查 `cst_radius` 的實現
2. ✅ 確認返回值是半徑還是直徑
3. 修正 `CST_Modeler.cst_curve()` 方法
4. 或者在設置 VSP 參數時乘以 2

**測試**:
- 用固定參數生成模型
- 檢查 Width 和 Height 是否為期望值
- 檢查視覺比例是否正確

### 第二步：研究 VSP Super_Ellipse 參數

**目標**: 找到實現上下非對稱的方法

**需要研究**:
1. VSP Super_Ellipse 是否有 Z 偏移參數？
2. 是否有 TopRadius/BottomRadius 參數？
3. File XSec 的檔案格式是什麼？
4. 如何生成和導入 File XSec？

**參考資料**:
- VSP API 文檔: `docs/VSP_API_Doc.html`
- VSP 範例檔案
- OpenVSP 論壇

### 第三步：實現上下兩條 CST 曲線

**推薦方案**: File XSec

**實現步驟**:
1. 根據 `gene` 參數生成上下兩條 CST 曲線
2. 計算截面輪廓點（上曲線 + 下曲線）
3. 保存為 VSP File XSec 格式
4. 使用 `XS_FILE_FUSE` 導入
5. 測試結果

---

## 當前優先級

### 🔥 立即修正（阻礙測試）
1. [ ] 修正 CST 尺寸計算（半徑 vs 直徑）
2. [ ] 測試尺寸是否正確

### 🔍 研究階段
1. [ ] 研究 VSP Super_Ellipse 完整參數列表
2. [ ] 研究 File XSec 格式和用法
3. [ ] 查閱 VSP API 文檔找上下非對稱方法

### 🚀 實現階段（研究完成後）
1. [ ] 實現上下兩條 CST 曲線生成
2. [ ] 實現 File XSec 導入
3. [ ] 測試非對稱模型

---

## 參考代碼位置

### CST 計算
- **原始正確版本**: `src/geometry/cst_geometry_math_driven.py:170-175`
- **當前問題版本**: `src/optimization/hpa_asymmetric_optimizer.py:305-314`

### VSP 截面設置
- **Super_Ellipse**: `src/optimization/hpa_asymmetric_optimizer.py:290-314`
- **需要研究**: File XSec 用法

---

## 下一步行動

**立即執行**:
1. 修正 `CST_Modeler.cst_curve()` 或在設置時 *2
2. 測試尺寸是否正確
3. 創建測試腳本驗證尺寸

**後續研究**:
1. 查閱 VSP API 文檔找 File XSec 用法
2. 查看是否有範例
3. 實現上下兩條 CST 曲線

---

**最後更新**: 2026-01-04 21:30
**狀態**: 分析完成，等待修正
