# Fairing Modeling Math Review Request

請你扮演一位重視物理合理性、幾何一致性、與低速流線體設計經驗的空氣動力與幾何建模顧問。

你現在**看不到任何原始程式碼**，只能根據我下面提供的數學定義、參數意義、建模流程與假設來審查這個整流罩參數化方法。請你不要假設還有其他未說明的實作細節。

你的任務不是幫我寫 code，而是從**物理與數學**角度判斷這套建模方式是否有盲點、不合理之處、隱含矛盾、過度耦合、自由度不足、自由度浪費、幾何連續性風險、或空力上容易誤導優化器的地方。

## Output Requirement

你的回覆**必須直接輸出為一份 Markdown 文件**，不要先說客套話，也不要輸出任何非 Markdown 的前言。

請直接從一級標題開始，並使用以下結構：

```md
# Fairing Math Review

## 1. Executive Summary

## 2. What Looks Reasonable

## 3. Main Mathematical / Physical Concerns

## 4. Hidden Couplings and Identifiability Issues

## 5. Geometry Continuity and Shape-Control Risks

## 6. Aerodynamic Plausibility Risks

## 7. Priority Fixes

## 8. Suggested Alternative Parameterizations

## 9. Final Verdict
```

額外要求：

- 全程只用 Markdown。
- 不要寫程式碼。
- 如果你做推論，請明確標記「這是推論」。
- 請把問題依嚴重度分成高、中、低。
- 每一個 concern 都要說清楚：
  - 問題是什麼
  - 為什麼它在數學或物理上可能有問題
  - 它最可能造成什麼設計偏差
  - 你建議怎麼改
- 最後一定要給一個明確結論：
  - 「大致合理，可繼續用」
  - 「可用於早期概念，但不適合當主要優化參數化」
  - 「有明顯結構性問題，建議重構」

## Problem Context

這是一個低速人力飛機整流罩的參數化建模方法。目標不是直接做高保真 CFD，而是先用它當作幾何生成與早期優化的主參數化方式，再把少數候選拿去做更高保真驗證。

我現在只想請你審查：

- 這套參數化在數學上是否一致
- 它的自由度配置是否合理
- 它是否會產生不自然或難以控制的幾何
- 它是否可能把優化器推向物理上不漂亮但數學上可行的形狀
- 它是否有不必要的耦合或多餘變數
- 它的尾段處理是否合理
- 它的截面模型是否合理
- 它是否適合作為低速流線體整流罩的主參數化

## Parameters

這個模型有 20 個輸入參數：

### Main size parameters

- `L`: 總長度
- `W_max`: 最大全寬
- `H_top_max`: 上半部最大高度
- `H_bot_max`: 下半部最大高度

### CST parameters

- `N1`: 前段 class parameter
- `N2_top`: 上邊界尾段 class parameter
- `N2_bot`: 下邊界尾段 class parameter
- `w0, w1, w2, w3`: 四個 Bernstein 權重

### Position parameters

- `X_max_pos`: 最大截面位置，範圍在 `[0,1]`
- `X_offset`: 與騎乘者/踏板相對位置有關的參數，但它**不直接改變外形方程式**

### Cross-section shape parameters

- `M_top, N_top`: 上半部超橢圓截面參數
- `M_bot, N_bot`: 下半部超橢圓截面參數

### Tail blending parameters

- `tail_rise`: 尾端收斂到的共同高度
- `blend_start`: 尾段混合開始位置
- `blend_power`: 尾段混合冪次

## Coordinate Definition

定義無因次縱向座標：

- `psi ∈ [0,1]`
- `x = L psi`

截面站位不是等距，而是採用全餘弦分布：

- `psi_i = 0.5 (1 - cos(pi i / (n-1)))`
- `i = 0,1,...,n-1`

也就是前後端截面較密，中間較疏。

## Core CST Definition

Class function:

- `C(psi) = psi^(N1) (1 - psi)^(N2)`

Shape function:

- `S(psi) = sum_{k=0}^3 w_k B_k^3(psi)`

其中三次 Bernstein basis 為：

- `B_k^3(psi) = C(3,k) psi^k (1-psi)^(3-k)`

展開後可寫成：

- `S(psi) = w0 (1-psi)^3 + 3 w1 psi (1-psi)^2 + 3 w2 psi^2 (1-psi) + w3 psi^3`

原始 CST 曲線：

- `f_raw(psi) = C(psi) S(psi)`

## Peak-Position Remapping

這個模型不是直接讓峰值由 `N1/(N1+N2)` 自然決定，而是另外指定 `X_max_pos`。

先定義原本 class function 的 nominal peak location：

- `psi_nom = N1 / (N1 + N2)`

接著引入一個單調三次映射 `g(psi)`，滿足：

- `g(0) = 0`
- `g(X_max_pos) = psi_nom`
- `g(1) = 1`

然後真正拿去計算 CST 的座標不是 `psi`，而是：

- `psi_eval = g(psi)`

因此被評估的原始曲線改成：

- `f_raw_remap(psi) = C(g(psi)) S(g(psi))`

## Peak Normalization

這個模型會把離散曲線的峰值重新正規化，強制最大值精確等於指定目標尺寸。

若目標峰值為 `H_target`，則最終曲線為：

- `f(psi) = H_target * f_raw_remap(psi) / max_j f_raw_remap(psi_j)`

也就是：

- 形狀主要由 `N1, N2, w0..w3` 與 `X_max_pos` 決定
- 但峰值大小會被額外縮放成指定尺寸

## Width Modeling

半寬曲線 `w(x)` 的建法是：

- `N2_avg = (N2_top + N2_bot) / 2`
- `w(x) = CST(psi; H_target = W_max/2, N1, N2_avg, w0..w3, X_max_pos)`

注意：

- `W_max` 是全寬
- 真正進模型的是 `W_max/2`

所以總寬度為：

- `W(x) = 2 w(x)`

## Upper and Lower Boundary Modeling

上、下邊界各自獨立建模：

- `z_u,CST(x) = CST(psi; H_target = H_top_max, N1, N2_top, w0..w3, X_max_pos)`
- `z_l,CST(x) = - CST(psi; H_target = H_bot_max, N1, N2_bot, w0..w3, X_max_pos)`

因此：

- 上邊界為正
- 下邊界先由正的 CST 高度生成，再整條取負號

## Tail Blending

尾段不是自然收斂到 `z=0`，而是上下邊界都收斂到共同的尾端高度 `tail_rise`。

混合因子定義為：

- 若 `psi < blend_start`，`beta(psi) = 0`
- 若 `psi >= blend_start`，`beta(psi) = ((psi - blend_start)/(1 - blend_start))^(blend_power)`

先得到初步混合後的上下邊界：

- `z_u,target = (1 - beta) z_u,CST + beta tail_rise`
- `z_l,target = (1 - beta) z_l,CST + beta tail_rise`

因此尾端理論上為：

- `z_u(1) = z_l(1) = tail_rise`

也就是尾端厚度趨近於 0，但尾點不一定在 `z=0`，而是在 `z=tail_rise`。

## Monotonic Tail Patch

在上述混合後，模型還會額外做一個經驗式修正，避免尾段在接近 `tail_rise` 的時候出現「先超過目標，再回來」的拐點。

### Upper surface patch

找第一個 `psi = psi_u*` 使得：

- `z_u,target <= 1.1 tail_rise`

從 `psi_u*` 到 `1`，改成線性插值：

- `z_u(psi) = z_u* + (tail_rise - z_u*) (psi - psi_u*) / (1 - psi_u*)`

並強制：

- `z_u* >= tail_rise`

### Lower surface patch

找第一個 `psi = psi_l*` 使得：

- `z_l,target >= 0.9 tail_rise`

從 `psi_l*` 到 `1`，改成線性插值：

- `z_l(psi) = z_l* + (tail_rise - z_l*) (psi - psi_l*) / (1 - psi_l*)`

並強制：

- `z_l* <= tail_rise`

所以尾段並不是純 CST，而是：

- `CST + remap + normalization + empirical tail blend patch`

## Reconstructed Section Quantities

為了生成實際截面，模型會把上下邊界轉成：

- 總高度 `H(x) = z_u(x) - z_l(x)`
- 幾何中心 `z_c(x) = (z_u(x) + z_l(x)) / 2`

因此每個站位 `x` 的截面主參數為：

- 半寬 `w(x)`
- 總高度 `H(x)`
- 中心高度 `z_c(x)`

## Cross-Section Model

每個中間截面採用上下非對稱超橢圓。

對每個截面定義：

- `a = w(x)`
- `b = H(x)/2`

參數角 `theta ∈ [0, 2pi)`。

### Upper half

當 `0 <= theta <= pi`：

- `y(theta) = a sign(cos theta) |cos theta|^(2/p_top)`
- `z(theta) = z_c + b |sin theta|^(2/p_top)`

### Lower half

當 `pi < theta < 2pi`：

- `y(theta) = a sign(cos theta) |cos theta|^(2/p_bot)`
- `z(theta) = z_c - b |sin theta|^(2/p_bot)`

## Important Implementation Detail About Section Exponents

這裡有一個很重要的事實，請特別評論其合理性：

雖然輸入參數名義上有 `M_top, N_top, M_bot, N_bot` 四個截面參數，但在目前這份數學摘要中，實際用於截面幾何與 proxy 幾何的是：

- `p_top = (M_top + N_top) / 2`
- `p_bot = (M_bot + N_bot) / 2`

也就是：

- 上半部實際只剩一個平均指數 `p_top`
- 下半部實際只剩一個平均指數 `p_bot`

這可能代表輸入參數的獨立性被弱化。

請你重點判斷：

- 這樣的平均化是否合理
- 這是否造成變數冗餘
- 這是否代表參數可識別性不好
- 這是否會讓優化器浪費自由度

## Tangent / Slope Handling

上、下表面的縱向切線角不是由封閉解析式直接求，而是由離散差分近似：

對上表面：

- `dz_u/dx ≈ (z_u(x_{i+1}) - z_u(x_{i-1})) / (x_{i+1} - x_{i-1})`
- `theta_top = atan(dz_u/dx)`

對下表面：

- `dz_l/dx ≈ (z_l(x_{i+1}) - z_l(x_{i-1})) / (x_{i+1} - x_{i-1})`
- `theta_bottom = - atan(dz_l/dx)`

下表面多一個負號，是為了配合外部幾何系統對 bottom tangent 的角度定義。

## Hidden Modeling Assumptions

請把以下假設是否合理一一檢查：

1. 同一個 `N1` 同時控制寬度、上表面、下表面的前段 class behavior。
2. 同一個 `X_max_pos` 同時控制寬度峰值與上下高度峰值位置。
3. 同一組 `w0..w3` 同時控制寬度、上表面、下表面的 shape function。
4. 左右方向的尾部行為用 `N2_avg = (N2_top + N2_bot)/2` 近似。
5. 上下尾端都收斂到同一個 `tail_rise`。
6. `X_offset` 不參與幾何方程，只參與約束判定。
7. 尾段連續性主要靠經驗式 patch 保證，而不是由參數化本身自然保證。

## What I Most Want You to Judge

請你特別回答下面這些問題：

1. 這套方法在數學上是否自洽？
2. 這套方法的自由度配置是否合理？
3. 是否存在過度耦合，導致某些形狀特徵其實不能獨立控制？
4. 是否存在冗餘變數，讓優化器在搜索時浪費維度？
5. `X_max_pos + peak remapping + peak normalization` 的組合是否合理？
6. `tail_rise + blend_start + blend_power + monotonic patch` 是否是合理的尾段建模方式？
7. 尾端收斂到共同 `tail_rise` 而不是 `z=0`，在幾何與空力上是否自然？
8. 用同一組 `w0..w3` 同時控制寬度與上下高度，是否太過綁定？
9. 用平均後的 `p_top, p_bot` 表示上下截面超橢圓，是否足夠？
10. 如果目標是低速流線體整流罩的早期優化，這套方法夠不夠好？
11. 如果不夠好，你最建議的替代參數化是什麼？

## Review Standard

請你不要只說「這大致可用」或「這看起來合理」。

我需要的是具有批判性的專業審查，請從下列角度系統性評估：

- 數學一致性
- 參數可識別性
- 幾何連續性
- 局部可控性
- 對優化器是否友善
- 是否容易產生假性最佳解
- 是否容易產生空力上不自然但數學上可行的形狀
- 是否符合低速流線體設計直覺

## Final Instruction

請你最後務必明確表態：

- 這個模型是否適合繼續作為主參數化
- 如果只允許小修，最值得優先改的 3 件事是什麼
- 如果允許重構，你最推薦的替代建模方向是什麼

再次提醒：你的整份回覆必須直接是一份 Markdown 文件，不要輸出任何程式碼。
