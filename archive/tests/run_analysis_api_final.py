import openvsp as vsp
import os

# --- 1. 環境設定 ---
rho = 1.1839
mu = 1.8371e-05
velocity = 6.5
analysis_name = "ParasiteDrag"  # 注意：通常是沒有空格的

# --- 2. 分析函數 ---
def run_vsp_analysis(filename):
    print(f"   正在讀取: {filename} ...")
    vsp.ClearVSPModel()
    vsp.ReadVSPFile(filename)
    
    # 檢查分析名稱是否正確 (只在第一次執行時檢查)
    # 我們列出所有可用的分析，確保名字對不對
    all_analyses = vsp.ListAnalysis()
    if analysis_name not in all_analyses:
        print(f"   ⚠️ 警告：找不到 '{analysis_name}'，可用的有：")
        print(all_analyses)
        return None, None

    # 設定預設值
    vsp.SetAnalysisInputDefaults(analysis_name)
    
    # --- 自動偵錯參數名稱 (關鍵步驟) ---
    # 如果不知道是 Vinf 還是 V_inf，我們先印出來看
    # print(f"   [{analysis_name}] 可用參數:")
    # vsp.PrintAnalysisInputs(analysis_name) 

    # 設定流體參數 (使用字串直接設定)
    # 嘗試設定 Vinf (如果報錯，請看上面的 PrintAnalysisInputs 輸出)
    try:
        vsp.SetDoubleAnalysisInput(analysis_name, "Rho", [rho])
        vsp.SetDoubleAnalysisInput(analysis_name, "Vinf", [velocity]) # 注意這裡是 Vinf
        vsp.SetDoubleAnalysisInput(analysis_name, "Mu", [mu])
    except:
        print("   ❌ 設定參數失敗，可能是參數名稱不對 (例如 Vinf vs V_inf)")
        vsp.PrintAnalysisInputs(analysis_name)
        return None, None
        
    # 執行分析
    # 這裡會自動計算濕面積，不需要 ComputeGeom
    print("   執行分析中...")
    vsp.ExecAnalysis(analysis_name)
    
    # 讀取結果
    try:
        # CDo 總值
        cd_total = vsp.GetDoubleAnalysisData(analysis_name, "Tot_CDo", [0])
        # 濕面積
        s_wet = vsp.GetDoubleAnalysisData(analysis_name, "Tot_Wet_Area", [0])
        # 參考面積
        s_ref = vsp.GetDoubleAnalysisData(analysis_name, "Sref", [0])
        
        # 計算真實阻力 (Newton)
        q = 0.5 * rho * (velocity ** 2)
        drag_force = q * s_ref * cd_total
        
        return drag_force, s_wet
    except:
        print("   ❌ 讀取結果失敗，請檢查變數名稱。")
        # 列印所有結果變數名稱供參考
        # doc = vsp.GetAnalysisDoc(analysis_name)
        # print(doc)
        return None, None

# --- 3. 主程式 ---
print("🚀 啟動 OpenVSP API 分析器 (String Mode)...")
print(f"目標速度: {velocity} m/s")
print("-" * 60)
print(f"{'設計名稱':<25} | {'濕面積 (m^2)':<12} | {'阻力 (N)':<10}")
print("-" * 60)

target_files = ["Type_A_Standard.vsp3", "Type_B_HighSpeed.vsp3", "Type_C_Comfort.vsp3"]

for f in target_files:
    if os.path.exists(f):
        drag, area = run_vsp_analysis(f)
        if drag is not None:
            print(f"{f.replace('.vsp3', ''):<25} | {area:<12.4f} | {drag:<10.5f}")
    else:
        print(f"❌ 找不到檔案: {f}")

print("-" * 60)
print("💡 如果還是失敗，請務必使用我在上一次對話給你的")
print("   『run_analysis_math.py』(純數學版)，那個絕對不會有 API 問題！")