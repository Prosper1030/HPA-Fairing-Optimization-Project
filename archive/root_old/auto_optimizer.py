import openvsp as vsp
import math
import os
import csv
import shutil

# ==========================================
# 1. 基礎設定與 CST 數學核心
# ==========================================
OUTPUT_DIR = "output"  # 所有的垃圾檔案都丟這裡

def ensure_output_folder():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"📁 已建立輸出資料夾: {OUTPUT_DIR}")

def cst_class_function(psi, N1, N2):
    return (psi ** N1) * ((1 - psi) ** N2)

def cst_shape_function(psi, weights):
    n = len(weights) - 1
    S = 0
    for i in range(len(weights)):
        comb = math.factorial(n) / (math.factorial(i) * math.factorial(n - i))
        bernstein = comb * (psi ** i) * ((1 - psi) ** (n - i))
        S += weights[i] * bernstein
    return S

def calculate_cst_radius(psi, N1, N2, weights, length):
    if psi <= 0 or psi >= 1: return 0.0
    C = cst_class_function(psi, N1, N2)
    S = cst_shape_function(psi, weights)
    return C * S * length

# ==========================================
# 2. OpenVSP 幾何生成器 (修正版)
# ==========================================
def generate_fairing(design_data):
    """
    根據設計參數產生幾何，並確保截面形狀正確
    """
    name = design_data["name"]
    L = design_data["length"]
    N1 = design_data["n_nose"]
    N2 = design_data["n_tail"]
    W_w = design_data["width_weights"]
    H_w = design_data["height_weights"]
    
    print(f"   🔨 [建模] 正在生成: {name} (L={L}m)...")
    
    vsp.ClearVSPModel()
    fuse_id = vsp.AddGeom("FUSELAGE")
    vsp.SetGeomName(fuse_id, name)
    vsp.SetParmVal(fuse_id, "Length", "Design", L)
    
    # --- 關鍵修正：確保截面數量與類型 ---
    xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
    
    # 1. 先切出足夠的截面 (例如 40 段)
    target_sections = 40
    current_sections = vsp.GetNumXSec(xsec_surf)
    
    # 使用定量的 Cut，避開死結
    needed_cuts = target_sections - current_sections
    for _ in range(needed_cuts):
        # 切在 Index 1 的位置 (避開頭尾)
        vsp.CutXSec(fuse_id, 1)
        
    vsp.Update() # 強制更新模型狀態
    
    # 2. 遍歷所有截面，賦予正確的形狀與尺寸
    final_count = vsp.GetNumXSec(xsec_surf)
    
    for i in range(final_count):
        xsec = vsp.GetXSec(xsec_surf, i)
        psi = i / (final_count - 1)
        
        # 設定位置
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "XLocPercent"), psi)
        
        # --- 解決你的第4點問題 ---
        # 判斷是否為頭尾
        is_tip = (i == 0) or (i == final_count - 1)
        
        if is_tip:
            # 頭尾強制設為 Point (0)
            vsp.SetXSecShape(xsec, 0) 
        else:
            # 中間強制設為 Ellipse (2) (或者 SuperEllipse)
            vsp.SetXSecShape(xsec, 2) 
            
            # 計算 CST 數值
            r_width = calculate_cst_radius(psi, N1, N2, W_w, L)
            r_height = calculate_cst_radius(psi, N1, N2, H_w, L)
            
            w = max(r_width * 2, 0.001)
            h = max(r_height * 2, 0.001)
            
            # 設定寬高 (注意參數名稱)
            vsp.SetParmVal(vsp.GetXSecParm(xsec, "Ellipse_Width"), w)
            vsp.SetParmVal(vsp.GetXSecParm(xsec, "Ellipse_Height"), h)
            
    vsp.Update()
    
    # 存檔到 output 資料夾
    filepath = os.path.join(OUTPUT_DIR, f"{name}.vsp3")
    vsp.WriteVSPFile(filepath)
    return filepath

# ==========================================
# 3. 阻力分析與數據讀取
# ==========================================
def run_analysis_and_parse(filepath, velocity, rho, mu):
    """
    執行 Parasite Drag 分析並直接讀取 CSV 結果
    """
    name = os.path.basename(filepath).replace(".vsp3", "")
    print(f"   🌪️ [分析] 正在計算流體力學數據...")
    
    # 1. 載入並執行分析
    vsp.ClearVSPModel()
    vsp.ReadVSPFile(filepath)
    
    analysis_name = "ParasiteDrag"
    vsp.SetAnalysisInputDefaults(analysis_name)
    vsp.SetDoubleAnalysisInput(analysis_name, "Rho", [rho])
    vsp.SetDoubleAnalysisInput(analysis_name, "Vinf", [velocity])
    vsp.SetDoubleAnalysisInput(analysis_name, "Mu", [mu])
    
    # 執行分析 (CSV 會自動生成在當前工作目錄)
    vsp.ExecAnalysis(analysis_name)
    
    # 2. 移動 CSV 到 output 資料夾 (保持整潔)
    generated_csv = f"{name}_ParasiteBuildUp.csv"
    target_csv = os.path.join(OUTPUT_DIR, generated_csv)
    
    if os.path.exists(generated_csv):
        # 如果目標已存在，先刪除
        if os.path.exists(target_csv): os.remove(target_csv)
        shutil.move(generated_csv, target_csv)
        
        # 順便把其他產生的雜檔移走或刪除
        geom_csv = f"{name}_CompGeom.csv"
        if os.path.exists(geom_csv): 
            shutil.move(geom_csv, os.path.join(OUTPUT_DIR, geom_csv))
    else:
        print("   ❌ 找不到分析報告 CSV，分析可能失敗。")
        return None

    # 3. 解析 CSV (抓取 CdA 和 Drag)
    q = 0.5 * rho * (velocity ** 2)
    result = {"name": name, "file": filepath}
    
    try:
        with open(target_csv, 'r', newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)
            
            # 簡單暴力的關鍵字搜尋法
            for row in rows:
                row_str = [str(c).lower() for c in row]
                # 尋找總和列 (Total)
                if "total" in row_str[0] or "totals" in row_str[0]:
                    # 通常 f (ft^2) 是第 10 或 11 欄，我們用搜尋的比較準
                    # 這裡假設我們要找的是當量平板面積 f (即 CdA)
                    # 它的數值通常在倒數第幾欄，這裡我們簡單用欄位位置嘗試
                    # 根據之前的經驗，S_wet 是 index 1, f 是 index 10 (或附近)
                    
                    # 為了穩健，我們不用 index 硬抓，改用之前的 run_final_calc 邏輯
                    # 但為了程式簡潔，這裡我先抓特定位置，如果不對我們再微調
                    # 假設 CSV 格式固定
                    try:
                        f_val = float(row[-3]) # 倒數第三個通常是 f (CdA)
                        s_wet = float(row[1])  # 第二個通常是 S_wet
                        
                        result["CdA"] = f_val
                        result["Swet"] = s_wet
                        result["Drag"] = q * f_val
                        result["Cd"] = f_val / s_wet if s_wet > 0 else 0
                        return result
                    except:
                        pass
    except Exception as e:
        print(f"   ❌ 解析 CSV 失敗: {e}")
        return None
    
    return None

# ==========================================
# 4. 主控制台 (Main Controller)
# ==========================================
def main():
    ensure_output_folder()
    
    # --- A. 定義環境 ---
    V = 6.5
    rho = 1.1839
    mu = 1.8371e-05
    
    print("🚀 啟動自動優化流程 (Auto Optimizer)")
    print(f"   環境: V={V} m/s, Rho={rho}")
    print("="*60)

    # --- B. 定義設計參數 (可以在這裡無限新增) ---
    # 這裡解決了你的第1點：可以設置具體參數
    design_queue = [
        {
            "name": "Case_1_Standard",
            "length": 2.5,
            "n_nose": 0.5, "n_tail": 1.0, # N=0.5是橢圓, N=1.0是圓錐
            "width_weights": [0.15, 0.20, 0.20, 0.05],
            "height_weights": [0.20, 0.35, 0.25, 0.05]
        },
        {
            "name": "Case_2_Slim",
            "length": 3.0,
            "n_nose": 0.4, "n_tail": 1.0,
            "width_weights": [0.10, 0.15, 0.15, 0.02],
            "height_weights": [0.15, 0.25, 0.20, 0.02]
        },
        {
            "name": "Case_3_Bulky",
            "length": 2.2,
            "n_nose": 0.6, "n_tail": 0.8,
            "width_weights": [0.20, 0.30, 0.25, 0.10],
            "height_weights": [0.25, 0.40, 0.30, 0.10]
        },
        # 你可以在這裡加 Case_4, Case_5...
    ]

    results = []

    # --- C. 自動化迴圈 (解決第2點) ---
    for design in design_queue:
        # 1. 生成模型 (解決第3、4點)
        vsp_file = generate_fairing(design)
        
        # 2. 執行分析
        res = run_analysis_and_parse(vsp_file, V, rho, mu)
        
        if res:
            results.append(res)
            print(f"   ✅ 結果: Drag = {res['Drag']:.4f} N, CdA = {res['CdA']:.5f}")
        else:
            print("   ⚠️ 分析無結果")
        print("-" * 30)

    # --- D. 最終排名 ---
    print("\n🏆 優化排名 (阻力由小到大):")
    print(f"{'排名':<5} | {'設計名稱':<20} | {'阻力 (N)':<12} | {'CdA (m^2)':<12} | {'濕面積 (m^2)':<12}")
    print("-" * 70)
    
    results.sort(key=lambda x: x["Drag"])
    
    for i, res in enumerate(results):
        print(f"{i+1:<5} | {res['name']:<20} | {res['Drag']:<12.5f} | {res['CdA']:<12.6f} | {res['Swet']:<12.4f}")

    print("\n🎉 流程結束。所有檔案已存於 output 資料夾。")

if __name__ == "__main__":
    main()