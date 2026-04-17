# HPA Fairing Project Future Roadmap

更新日期: 2026-04-17

## 1. 核心原則

這個專案後續的主線，不是追求「程式內部結果一致」而已，而是建立一條**物理上合理、工程上可信、可重現**的低速整流罩分析與優化工作流。

幾個固定原則:

- `proxy` 的角色是搜尋器，不是假裝成真值。
- `SU2` 的角色是高保真驗證，但前提是它自己的 workflow 要先被驗證可信。
- `OpenVSP` 保留為 legacy compare / `.vsp3` 匯出工具，不再是主分析或主預覽路線。
- 不接受只對單一 case 有效的調參；任何方法都必須對整個 fairing 設計家族有可用性。

## 2. 目前狀態

### 已有能力

- 已可用 `proxy` 跑完整 GA。
- 已可建立 `SU2` shortlist 工作包。
- 已有 `gmsh_3d` 與 `axisymmetric_2d` 兩條 SU2 mesh 路線。
- 已加入 `SU2` 內建 Cauchy convergence 判定，並補上工程穩定性檢查。
- 已可輸出 `.vsp3` 供 OpenVSP GUI 檢視。

### 目前限制

- `proxy` 目前仍屬於 semi-empirical model，不能當最終真值。
- `SU2` workflow 還沒有完成多案例驗證，尚不能直接宣稱為最終可信基準。
- 專案目前缺少不依賴 OpenVSP 的輕量 3D 預覽方式。
- 專案目前缺少對 `SolidWorks / ANSYS` 友善的通用 CAD 匯出。

## 3. 第一優先: 建立可信的 SU2 Workflow

這一階段的目標不是做漂亮的 benchmark，而是建立一條**敢相信的 SU2 工作流**。

### 3.1 多案例驗證

不要只看單一最佳解。至少挑 `5~10` 個代表性設計，覆蓋以下類型:

- 細長型
- 短胖型
- 最大截面偏前
- 最大截面偏後
- 尾段較激進
- 尾段較保守

### 3.2 必做檢查

每個案例都要檢查:

- solver 是否正常收斂
- `SU2` 內建 `CONV_FIELD=DRAG` / `CONV_CAUCHY_*` 是否通過
- 尾段 `Cd` 擺幅是否穩定
- mesh 加密後結果是否趨穩
- 幾何換形狀後 mesh 是否仍可穩定生成
- farfield/domain 大小是否不再主導結果

### 3.3 通過門檻

只有同時滿足以下條件，才可稱該案例的 SU2 結果「可信」:

- `SU2` 內建收斂判斷為 `Converged = true`
- `CdSwingPercentLast10 <= 0.2%`
- `LastCauchyCd` 達到 config 中的 Cauchy criterion
- `fine -> finer` 的 `Cd` 變化小於 `5%`
- 換幾何後不出現大量 mesh failure 或 solver instability

如果只是在某一個案例上看起來很穩，但換設計就失效，則判定這條 workflow **不可用**。

### 3.4 與 ANSYS 對齊

當有可用的 ANSYS 對照案例時，必須明確對齊:

- 幾何
- 流速
- 空氣密度與黏度
- 參考面積
- 阻力定義
- 邊界條件
- 是否為 laminar / transition / turbulence

目標不是要求 SU2 和 ANSYS 完全一樣，而是確認兩者在合理工程級距內，且偏差有規律可解釋。

## 4. 第二優先: 用可信 SU2 來約束 proxy

只有在第 3 節完成之後，才進行 proxy 校正。

### 保留的部分

- `Cf * FF * Swet` 這種黏性阻力骨架保留
- 幾何量測骨架保留

### 可調整的部分

- 壓力阻力風險項
- 尾段分離/回收相關 heuristic
- laminar fraction 的量級與敏感度

### 明確禁止

- 禁止用單一 case 把 proxy 調成「很像 SU2」
- 禁止犧牲泛化性換取某一個案例的漂亮誤差

### proxy 的成功標準

- 在代表性案例集上排序大致正確
- 絕對值誤差可接受
- 壞幾何會被 proxy 正確懲罰
- 不會把 GA 系統性導向高保真明顯不好的方向

## 5. 第三優先: 再跑大規模 GA

只有在 `SU2 workflow` 與 `proxy` 都通過基本可信度檢查後，才進行大規模優化。

建議順序:

1. 用修正後的 `proxy` 跑大規模 GA，例如 `80 x 40`
2. 對最終 shortlist 進行 `SU2` 驗證
3. 若有 ANSYS，可對最終 `top cases` 做交叉確認

這樣的意義是:

- `proxy` 負責效率
- `SU2` 負責驗證
- `ANSYS` 負責最後外部比對

## 6. 第四優先: 提升使用體驗

### 6.1 輕量 3D 預覽器

需要新增一個**不依賴 OpenVSP GUI** 的輕量預覽器。

v1 建議做法:

- 分析後直接輸出單檔 `HTML`
- 可旋轉、縮放、切 side/top/front 視角
- 顯示幾何與基本指標
- 不做 CFD 雲圖

目的:

- 快速看幾何是否合理
- 減少對 OpenVSP 外部 GUI 的依賴
- 讓 batch / best case 更容易比較

### 6.2 外部 CAD / CAE 匯出

需要新增對下游工具友善的匯出功能。

優先順序:

1. `STEP / BREP`
2. `STL`
3. `.vsp3` 保留為 legacy

原因:

- `SolidWorks / ANSYS / SpaceClaim` 更適合吃中性 CAD 實體格式
- `STL` 比較像 mesh 交換，不是首選 CAD 幾何交換
- `.vsp3` 太依賴 OpenVSP，不適合作為主資料交換格式

## 7. 不該做的事

以下方向要避免:

- 只為了讓 proxy 看起來像 SU2 而調參
- 只為了讓 SU2 結果看起來穩而忽略網格與物理設定
- 把單一案例調通就宣稱整條路線可用
- 把 OpenVSP 繼續當主流程核心
- 把「結果一致」誤認成「結果可信」

## 8. 下一個具體任務

最值得立即執行的下一組任務是:

1. 把 `run_su2_mesh_study.py` 擴成正式 multi-case study
2. 對 `5~10` 個代表性設計跑 `gmsh_3d + SU2`
3. 建立 `ReferenceReady / NotReferenceReady` 判定
4. 之後才進入 proxy 校正
5. 再往 `HTML preview` 與 `STEP/BREP export` 推進

如果這一輪多案例驗證失敗，就要先修 mesh / physics workflow，而不是急著跑更大規模的 GA。
