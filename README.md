# HPA Fairing Optimization Project

**低速整流罩快速分析工具，支援後續接 GA 與高保真驗證**

本專案目前的主線已從「OpenVSP 驅動的 GA 優化」調整為「快速代理分析為主，GA 與高保真驗證為延伸能力」。

現在最主要的 user-facing 入口是：

```bash
python scripts/analyze_fairing.py --gene <gene.json>
```

它會使用目前的 `fast_proxy` 阻力代理模型，直接輸出一組可閱讀的分析報告，而不是只回傳單一數字。

## 專案定位

- 主用途：分析低速整流罩外形的阻力特性與改善方向
- 正式主路徑：`fast_proxy`
- 可選 preset：
  - `none`：純低速整流罩空力分析
  - `hpa`：加入目前 HPA 專案使用的座艙 / 踏板 / 肩膀 / 尾長限制
- OpenVSP：保留為 legacy / benchmark / fallback 開發工具，不再是主分析方案
- SU2：作為最終 shortlist 驗證工具，現在可先產出驗證工作包，不進日常分析流程

## 快速開始

### 1. 建立環境

macOS / Linux：

```bash
source activate_env.sh
```

Windows PowerShell：

```powershell
. .\activate_env.ps1
```

詳細的 macOS 安裝流程請見 `docs/MAC_SETUP.md`。

### 2. 準備 gene JSON

分析工具目前只支援現有的 CST / gene 參數化輸入。gene 檔案必須包含以下 20 個欄位：

- `L`
- `W_max`
- `H_top_max`
- `H_bot_max`
- `N1`
- `N2_top`
- `N2_bot`
- `X_max_pos`
- `X_offset`
- `M_top`
- `N_top`
- `M_bot`
- `N_bot`
- `tail_rise`
- `blend_start`
- `blend_power`
- `w0`
- `w1`
- `w2`
- `w3`

如果你想先拿一份可直接修改的範例檔：

```bash
python scripts/analyze_fairing.py --write-example-gene example_gene.json
```

如果你只想先看必填欄位與範圍：

```bash
python scripts/analyze_fairing.py --show-required-fields
```

如果你的 gene 只想覆蓋少數欄位，也可以讓工具自動用範例值補齊其餘欄位：

```bash
python scripts/analyze_fairing.py \
  --gene partial_gene.json \
  --fill-missing-from-example
```

### 3. 執行單一設計分析

```bash
# 純低速整流罩分析
python scripts/analyze_fairing.py --gene path/to/gene.json

# 套用 HPA 幾何限制檢查
python scripts/analyze_fairing.py --gene path/to/gene.json --preset hpa

# 指定流場與輸出目錄
python scripts/analyze_fairing.py \
  --gene path/to/gene.json \
  --flow config/fluid_conditions.json \
  --out output/analysis/demo_case \
  --preset none
```

### 4. 查看報告輸出

每次分析都會產出一組 report bundle：

- `summary.json`：完整機器可讀結果
- `summary.md`：人可直接閱讀的摘要
- `side_profile.png`：外形側視圖
- `drag_breakdown.png`：黏滯阻力 / 壓力阻力拆解

### 5. 執行 batch 分析

如果你有一整批 gene JSON 想一起比較：

```bash
python scripts/analyze_fairing.py \
  --gene-dir path/to/gene_directory \
  --out output/analysis/batch_demo
```

batch 模式會：

- 對資料夾內每個 `.json` 各自建立一個子目錄
- 每個案例都產生自己的 `summary.json` / `summary.md` / 圖檔
- 在根目錄另外產生 `batch_summary.json` 與 `batch_summary.md`
- 依 `Drag` 由小到大做排名，方便快速比較候選外形
- 額外標記 `RepresentativeTags`，方便後續挑代表案例做 SU2 驗證

如果 batch 目錄裡有些 gene 只寫了部分欄位，也可以一起補齊：

```bash
python scripts/analyze_fairing.py \
  --gene-dir path/to/gene_directory \
  --fill-missing-from-example \
  --out output/analysis/batch_demo
```

## 分析結果內容

分析核心會固定輸出以下欄位：

- `Drag`
- `Cd`
- `Cd_viscous`
- `Cd_pressure`
- `Swet`
- `LaminarFraction`
- `XPeakAreaFrac`
- `TailAngles`
- `Quality`
- `Recommendations`
- `ConstraintReport`
- `PresetUsed`
- `Backend`

`Recommendations` 會直接給自然語句，例如：

- 把最大截面往前移一些
- 放緩下尾收縮
- 減少濕面積
- 優先改善尾段平滑度

## GA 優化

GA 仍然保留，而且現在預設走 `proxy` 路徑，不再依賴 OpenVSP 才能正常跑完整流程。

```bash
# 使用 config/ga_config.json 的預設值
python scripts/run_ga.py

# 自訂世代與族群
python scripts/run_ga.py --gen 50 --pop 20

# 明確指定 analysis mode
python scripts/run_ga.py --analysis-mode proxy

# 一鍵把 GA 結果整理成 SU2 shortlist 工作包
python scripts/run_ga.py --prepare-su2-shortlist --su2-shortlist-top 5
```

GA 的預設行為：

- 適應度主路徑使用 `proxy`
- 保存 `best_gene.json`
- 另外保存 `results.json`，包含最佳解的純空力摘要
- 會持續記錄每個已評估候選到 `logs/candidate_scores.jsonl`
- 最終 `.vsp3` 匯出預設關閉

如果你加上 `--prepare-su2-shortlist`，GA 完成後還會自動：

- 從已評估候選中挑出前 `N` 名有效設計
- 在 `<run_dir>/su2_shortlist` 產生 SU2 驗證工作包
- 在 `results.json` 補上 `su2_shortlist` 輸出摘要

如果你真的需要最佳解的 `.vsp3`：

```bash
python scripts/run_ga.py --final-vsp
```

## 設定檔

### `config/analysis_config.json`

分析工具預設設定：

- 預設 backend：`fast_proxy`
- 預設 preset：`none`
- 報告輸出開關

### `config/ga_config.json`

GA 設定保留給優化流程使用，目前預設：

- `fitness.analysis_mode = "proxy"`
- `output.export_final_vsp = false`

### `config/fluid_conditions.json`

流場條件可供分析工具與 GA 共用，例如：

```json
{
  "flow_conditions": {
    "velocity": { "value": 6.5, "unit": "m/s" },
    "density": { "value": 1.225, "unit": "kg/m^3" },
    "viscosity": { "value": 1.7894e-5, "unit": "kg/(m*s)" }
  }
}
```

## HPA Preset

`--preset hpa` 會額外檢查目前 HPA 專案使用的硬限制：

- 車架包覆
- 踏板寬度
- 肩膀寬度
- 肩膀上高
- 肩膀下高
- 機尾長度

`--preset none` 則只做純空力分析，不帶 HPA 專案特定限制。

## OpenVSP 與高保真驗證

### OpenVSP

OpenVSP 現在的定位是：

- 開發者用 benchmark / compare tool
- 舊流程相容
- 特定情況下的 fallback

它不再是主要 user-facing 分析方案，也不是推薦的日常工作流。

### SU2

SU2 現在的定位是「最終 shortlist 驗證」，不是日常分析 backend，也不是 GA 每代內圈的一部分。

目前可用的入口是：

```bash
# 從 batch 排名中取前 3 名，準備 SU2 工作包
python scripts/prepare_su2_shortlist.py \
  --batch-summary output/analysis/batch_demo/batch_summary.json \
  --top 3 \
  --out output/su2_shortlist/demo

# 或者直接在 GA 結束後一鍵產生
python scripts/run_ga.py \
  --prepare-su2-shortlist \
  --su2-shortlist-top 5

# 直接用單一 gene 準備工作包
python scripts/prepare_su2_shortlist.py \
  --gene path/to/gene.json \
  --out output/su2_shortlist/single_case

# 直接產生可跑的軸對稱 benchmark mesh
python scripts/prepare_su2_shortlist.py \
  --gene path/to/gene.json \
  --out output/su2_shortlist/axis_case \
  --mesh-mode axisymmetric_2d

# 用 GA 的 best_gene.json 準備工作包
python scripts/prepare_su2_shortlist.py \
  --best-gene output/hpa_run_xxx/logs/best_gene.json \
  --out output/su2_shortlist/best_case

# 對已經有 mesh 的 shortlist 實際執行 SU2
python scripts/run_su2_shortlist.py \
  --shortlist-dir output/su2_shortlist/demo

# 如果要用 MPI
python scripts/run_su2_shortlist.py \
  --shortlist-dir output/su2_shortlist/demo \
  --ranks 4

# 直接從 batch summary 挑代表案例做 multi-case mesh study
python scripts/run_su2_mesh_study.py \
  --batch-summary output/analysis/batch_demo/batch_summary.json \
  --representative-study \
  --representative-limit 6 \
  --out output/su2_mesh_study/demo
  # 不設 --representative-limit 時，預設會取 8 個（落在 5~10 之間）

# 如果只想跑特定 mesh profile
python scripts/run_su2_mesh_study.py \
  --batch-summary output/analysis/batch_demo/batch_summary.json \
  --representative-study \
  --profile fine \
  --profile finer \
  --out output/su2_mesh_study/demo
```

這個流程會為每個 case 產生：

- `gene.json`
- `summary.json` / `summary.md`
- `fairing_geometry.csv`
- `su2_case.cfg`
- `su2_runtime.cfg`
- `PUT_MESH_HERE.txt`
- `geometry_preview.html`
- `fairing_surface.stl`
- `fairing_surface.obj`
- `README.md`

如果你沒有特別指定 `--geometry-export`，目前預設就會幫你產出：

- `geometry_preview.html`
- `fairing_surface.stl`
- `fairing_surface.obj`

CLI 完成時也會直接把第一個 case 的預覽與 mesh 路徑印出來，方便你立刻打開檢查幾何。

如果你使用 `--mesh-mode axisymmetric_2d`，每個 case 還會多出：

- `fairing_mesh.su2`
- `mesh_metadata.json`

如果你有指定 `--geometry-export step` 或 `--geometry-export brep`，且當前尚未啟用 STEP/BREP 匯出器，對應輸出會記錄警告在
`validation_manifest.json` 與每個 case 的 `README.md`。

根目錄另外會產生：

- `validation_manifest.json`
- `validation_manifest.md`
- `shortlist_report.json`
- `shortlist_report.md`
- `run_all_su2_cases.sh`

其中最適合先閱讀的是 `shortlist_report.md`，它會把 shortlist 的 proxy score、Drag、Cd、來源代數與建議重點整理成一份比較報告。

如果你已經把 `.su2` mesh 放進各 case 資料夾，執行 `run_su2_shortlist.py` 後還會額外得到：

- `su2_result.json` / `su2_result.md`：每個 case 的 SU2 結果
- `su2_run_summary.json`
- `su2_run_summary.md`

如果你使用 `run_su2_mesh_study.py`，則會另外得到：

- `mesh_study_summary.json`
- `mesh_study_summary.md`
- 每個 case 各 profile 的子資料夾

`mesh_study_summary` 會整理：

- 每個 case 的 `ReferenceReady / NotReferenceReady`
- `fine -> finer` 的 `Cd` 變化
- Cauchy / `CdSwingPercentLast10` 檢查
- representative case selection coverage 與選取理由

目前的範圍是「準備可重現的 SU2 驗證工作包」：

- 只對 shortlist 候選做驗證
- 不進每代 GA 內圈
- 不幫你自動建 mesh
- 但現在已經可以在 mesh 準備好後直接啟動 SU2 求解

換句話說，它會把 proxy 基準、幾何表格與 SU2 starter config 都整理好；你只要把 mesh 放進 case 資料夾，就能用 `run_su2_shortlist.py` 或 `run_all_su2_cases.sh` 跑出第一版高保真比較基準。

如果你想先要一個「不用外部 mesher、可直接重跑」的比較基準，可以改用 `--mesh-mode axisymmetric_2d`。這會把 fairing 轉成面積等效的軸對稱截面，並自動建立 2D axisymmetric SU2 mesh。它不是最終 3D 高保真驗證，但很適合先建立一條比 proxy 更物理、又比手工 3D meshing 更輕量的基準路徑。

## 專案結構

```text
HPA-Fairing-Optimization-Project/
├── config/
│   ├── analysis_config.json
│   ├── fluid_conditions.json
│   └── ga_config.json
├── scripts/
│   ├── analyze_fairing.py
│   ├── prepare_su2_shortlist.py
│   ├── run_su2_shortlist.py
│   ├── run_ga.py
│   └── run_one_case.py
├── src/
│   ├── analysis/
│   │   ├── fairing_analysis.py
│   │   ├── fairing_drag_proxy.py
│   │   ├── drag_analysis.py
│   │   └── high_fidelity_validator.py
│   ├── optimization/
│   │   └── hpa_asymmetric_optimizer.py
│   └── math/
├── tests/
└── docs/
```

## 環境需求

- Python 3.11
- `numpy`
- `scipy`
- `matplotlib`
- `pymoo`：只在執行 GA 時需要
- OpenVSP：只在 legacy compare / `.vsp3` 匯出 / 舊流程時需要

安裝依賴：

```bash
python -m pip install -r requirements.txt
```

## 開發與測試

常用測試：

```bash
python3 -m unittest \
  tests.test_high_fidelity_validator \
  tests.test_fairing_analysis \
  tests.test_drag_proxy_metrics \
  tests.test_geometry_peak_position \
  tests.test_project_manager_serialization \
  tests.test_su2_axisymmetric_mesh \
  tests.test_run_ga_proxy
```

legacy compare benchmark 為 opt-in，只在本機具備 OpenVSP 時建議執行：

```bash
python tests/experimental/benchmark_proxy_vs_vsp.py --samples 4 --seed 42
```

## 版本方向

目前建議的開發路線：

1. 先把 `fast_proxy + CLI + report` 做穩
2. 再把 GA 視為批次搜尋工具接上同一套分析核心
3. 最後只對少數候選接入 SU2 類高保真驗證

---

**用途**：教育研究 / 低速整流罩設計探索
**單位**：成功大學航太工程學系
**最後更新**：2026-04-17
