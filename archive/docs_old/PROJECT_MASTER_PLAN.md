# **PROJECT_MASTER_PLAN**

---

# 專案代號：Project Aero-HPA (Human-Powered Aircraft Fairing Optimization)

版本： 3.0 (CST-SuperEllipse Architecture)

所屬單位： 國立成功大學 (NCKU) 航太系人力飛機團隊

目標賽事： 日本鳥人間大賽 (Japan Birdman Rally)

---

## 1\. 專案願景與物理挑戰 (Vision & Physics)

### 1\.1 核心任務

本專案旨在開發一套\*\*「全自動化的空氣動力外型優化系統」**，專門針對人力飛機（HPA）的**整流罩（Fairing）**進行設計。我們的目標是在滿足飛行員乘坐空間（幾何限制）的前提下，透過數學參數化建模與流體估算，找出**阻力面積 ($C_d \\cdot A$) 最小\*\*的最佳構型。

### 1\.2 物理環境與邊界條件

- **流場特徵**：低速、低雷諾數流場。

   - 飛行速度 $V\_{\\infty} \\approx 6.5 \\text{ m/s}$。

   - 雷諾數 $Re \\approx 4 \\times 10^5$ (基於機身長度)。

   - 此區間位於層流（Laminar）與紊流（Turbulent）的轉捩點，邊界層行為敏感。

- **阻力結構分析 (關鍵洞察)**：

   - 根據我們先前的實驗（Type A/B/C 對比），在低速下，**摩擦阻力 (Skin Friction Drag)** 佔總阻力的 85% 以上。(這部分可能還需要你思考查一下)

   - **反直覺結論**：細長型（High Fineness Ratio）的機身雖然壓差阻力（Pressure Drag）小，但因濕面積（Wetted Area）過大，總阻力反而最高。

   - **設計策略**：要在「縮短機身以減少濕面積」與「保持流線以避免氣流分離」之間尋求完美的數學平衡點。

---

## 2\. 數學建模核心：CST 與超橢圓 (Mathematical Core)

我們拒絕使用傳統的手繪或樣條曲線（Spline），改採 **CST (Class Shape Transformation)** 方法，原因在於其能用極少的參數定義出光順且連續（C2 Continuity）的航太級曲面。

### 2\.1 縱向輪廓控制：CST 方法

機身的寬度分佈 $W(\\psi)$ 與高度分佈 $H(\\psi)$ 均由以下公式定義：

$$R(\\psi) = C(\\psi) \\cdot S(\\psi) \\cdot L$$

其中 $\\psi = x/L$ 為無因次位置 ($0 \\le \\psi \\le 1$)。

#### **A. 類函數 (Class Function) $C(\\psi)$**

定義幾何的基礎拓樸結構。我們選擇 Airfoil-like (類翼型) 構型：



$$C\_{N1, N2}(\\psi) = \\psi^{N1} \\cdot (1-\\psi)^{N2}$$

- **$N1 = 0.5$**：機頭為圓形（Round Nose），確保氣流在停滯點附近的平滑過渡。

- **$N2 = 1.0$**：機尾為尖點（Sharp Tail），確保庫塔條件（Kutta Condition），避免尾部產生過大的尾流區。

#### **B. 形狀函數 (Shape Function) $S(\\psi)$**

用於微調曲線的局部特徵（如座艙位置的隆起）。使用 伯恩斯坦多項式 (Bernstein Polynomials)：



$$S(\\psi) = \\sum\_{i=0}^{n} w_i \\cdot \\frac{n!}{i!(n-i)!} \\cdot \\psi^i (1-\\psi)^{n-i}$$

- **設計變數**：權重向量 $\\mathbf{w} = \[w_0, w_1, ..., w_n\]$。

- 我們先前的測試使用了 4 階多項式 (4 weights)，未來可視需要增加階數以獲得更細緻的控制。

### 2\.2 橫向截面控制：超橢圓 (Super Ellipse)

這是目前的重大升級項目。為了在有限的迎風面積下最大化肩部空間，我們捨棄標準橢圓，改用**超橢圓**。

- 數學定義：

   

   $$\\left| \\frac{y}{a} \\right|^n + \\left| \\frac{z}{b} \\right|^n = 1$$

   - $a, b$：半寬與半高（由 CST 縱向公式計算得出）。

   - $n$：**超橢圓指數 (Super-ellipse exponent)**。

- **參數影響**：

   - $n=2.0$：標準橢圓（空間利用率一般）。

   - $n=2.5 \\sim 3.0$：接近圓角的矩形（Squircle），能顯著增加角落空間，讓飛行員肩膀更舒適，且不增加迎風面積。

- **OpenVSP 實作**：對應截面參數 `Super_Width` 與 `Super_Height`。

---

## 3\. 自動化工作流架構 (Automation Workflow)

由於 OpenVSP Python API 版本限制 (v3.42.3)，我們無法使用直接的物件回傳功能，必須建立一套基於「檔案交換」的穩健流程。

### **Step 1: 參數化生成 (Generator)**

- **輸入**：一組設計向量 $\\mathbf{D} = \[L, \\mathbf{w}\_{width}, \\mathbf{w}\_{height}, n\_{super}\]$。

- **幾何建構邏輯**：

   1. `vsp.AddGeom("FUSELAGE")`。

   2. `vsp.CutXSec`：切分約 40\~50 個截面。

   3. **截面屬性設定 (關鍵)**：

      - **Index 0 & -1 (頭尾)**：強制設為 `XS_POINT` (Type 0)，半徑為 0。

      - **Index 1 \~ -2 (中段)**：強制設為 `XS_ELLIPSE` (Type 2)。

      - **尺寸寫入**：依據 CST 算出的 $W(\\psi), H(\\psi)$ 設定 `Ellipse_Width`, `Ellipse_Height`。

      - **形狀微調**：設定 `Super_Width`, `Super_Height` 為 $n\_{super}$ (例如 2.5)。

   4. 匯出為 `.vsp3` 檔案至 `output/` 資料夾。

### **Step 2: 物理分析 (Analyzer)**

- **方法**：Component Buildup Method (Parasite Drag Tool)。不使用 CFD，以換取高迭代速度。

- **API 操作**：

   - 設定流體環境：$V=6.5, \\rho=1.1839$。

   - 執行 `vsp.ExecAnalysis("ParasiteDrag")`。

- **數據採礦**：

   - 系統會自動生成 `_ParasiteBuildUp.csv`。

   - Python 必須讀取此 CSV，鎖定 **Equivalent Flat Plate Area ($f$)** 欄位。

   - **目標函數**：$Cost = D = q \\cdot f$。

### **Step 3: 結果清洗與歸檔 (Archiver)**

- 將所有生成的雜項檔案（CSV, TXT, VSP3）統一移動至 `output/` 下的子目錄（如 `output/run_{timestamp}/`），保持專案整潔。

---

## 4\. 未來演算法規劃：遺傳演算法 (Genetic Algorithm)

目前的 `auto_``[optimizer.py](optimizer.py)` 僅是批次處理固定參數。下一階段（你將協助開發的部分），我們要將其升級為真正的**全域優化器**。

### 4\.1 為什麼選擇 GA？

- 整流罩的氣動特性是非線性的。

- 幾何限制（肩膀寬度）是不連續的懲罰函數。

- 傳統梯度下降法（Gradient Descent）容易陷入局部最佳解（Local Minima）。

### 4\.2 染色體編碼 (Chromosome Encoding)

每一個設計個體（Individual）將由以下基因組成：

Python

```
gene = [
    Length,          # 範圍: 2.0m ~ 3.0m
    W_weight_1,      # 寬度控制點 1
    W_weight_2,      # 寬度控制點 2
    H_weight_1,      # 高度控制點 1
    H_weight_2,      # 高度控制點 2
    N_Super_Ellipse  # 範圍: 2.0 ~ 3.0
]

```

### 4\.3 適應度函數 (Fitness Function)

我們要求的是最小值，故 Fitness 定義為：



$$Fitness = \\frac{1}{Drag + Penalty}$$

- **Drag**：由 OpenVSP 算出的真實阻力 (N)。

- **Penalty (懲罰項)**：

   - 在 $x \\approx 0.4L$ 處（預估肩膀位置），計算該處截面寬度 $W\_{shoulder}$。

   - 若 $W\_{shoulder} < 0.45 \\text{m}$，則 $Penalty = 1000$ (淘汰該設計)。