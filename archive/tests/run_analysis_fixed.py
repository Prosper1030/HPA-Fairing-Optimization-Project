import openvsp as vsp
import os
import math

# --- 1. 物理環境設定 (25度C, 標準大氣) ---
def get_atmosphere_properties(temp_c):
    T0 = 273.15 + temp_c       
    P0 = 101325.0              
    R = 287.05                 
    
    # 計算密度 (Rho)
    rho = P0 / (R * T0)
    
    # 計算動態黏滯係數 (Mu) - Sutherland 公式
    mu_ref = 1.716e-5
    T_ref = 273.15
    S = 110.4
    mu = mu_ref * ((T_ref + S) / (T0 + S)) * ((T0 / T_ref) ** 1.5)
    
    return rho, mu

# --- 2. 阻力分析主程式 ---
def analyze_drag(filename, velocity, rho, mu):
    # 清除並讀取檔案
    vsp.ClearVSPModel()
    vsp.ReadVSPFile(filename)
    
    # --- 設定 Parasite Drag 分析工具 ---
    analysis_name = "Parasite Drag"
    
    # 建立分析設定
    aid = vsp.FindAnalysis(analysis_name)
    vsp.SetAnalysisInputDefaults(aid)
    
    # 設定流體條件
    vsp.SetDoubleAnalysisInput(aid, "Rho", [0], rho)
    vsp.SetDoubleAnalysisInput(aid, "V_inf", [0], velocity)
    vsp.SetDoubleAnalysisInput(aid, "Mu", [0], mu)
    
    # 重要：執行分析 (它會自動計算濕面積)
    vsp.ExecAnalysis(aid)
    
    # --- 讀取結果 ---
    # 嘗試讀取總阻力係數 CDo
    # OpenVSP 的變數名稱有時候是 "Tot_CDo"
    cd_total = vsp.GetDoubleAnalysisData(aid, "Tot_CDo", [0])
    
    # 讀取分析算出來的濕面積 (Total Wetted Area)
    s_wet = vsp.GetDoubleAnalysisData(aid, "Tot_Wet_Area", [0])
    
    # 讀取參考面積 (通常 Parasite Drag 會用濕面積當參考，但我們要確認)
    s_ref = vsp.GetDoubleAnalysisData(aid, "Sref", [0])
    
    # --- 計算真實阻力 (Drag Force) [Newton] ---
    # D = 0.5 * rho * V^2 * S_ref * Cd
    q = 0.5 * rho * (velocity ** 2) # 動壓
    drag_force = q * s_ref * cd_total
    
    return drag_force, s_wet, cd_total

# --- 3. 批次執行 ---
print("🚀 開始空氣動力阻力分析 (修正版)...")
print("---------------------------------------------------------------")
print(f"環境條件: 25°C, 標準大氣壓")

V = 6.5 # m/s
rho, mu = get_atmosphere_properties(25.0)

print(f"空氣密度 (Rho): {rho:.4f} kg/m^3")
print(f"黏滯係數 (Mu) : {mu:.4e} kg/(m*s)")
print(f"飛行速度 (V)  : {V} m/s")
print(f"雷諾數 (Re/m) : {rho * V / mu:.2e} /m")
print("---------------------------------------------------------------")
print(f"{'設計名稱':<25} | {'濕面積 (m^2)':<12} | {'阻力 (Newton)':<15} | {'省力排名'}")
print("-" * 75)

# 指定讀取剛剛那三個檔案
target_files = ["Type_A_Standard.vsp3", "Type_B_HighSpeed.vsp3", "Type_C_Comfort.vsp3"]

results = []

for filename in target_files:
    if os.path.exists(filename):
        try:
            d_force, s_wet, cd = analyze_drag(filename, V, rho, mu)
            results.append({
                "name": filename,
                "drag": d_force,
                "area": s_wet
            })
        except Exception as e:
            print(f"❌ 分析 {filename} 失敗: {e}")
            # 如果失敗，試著列印出所有可用的數據名稱，方便除錯
            # aid = vsp.FindAnalysis("Parasite Drag")
            # print(vsp.GetDataNames(aid)) 
    else:
        print(f"⚠️ 找不到檔案: {filename}")

# 排序
results.sort(key=lambda x: x["drag"])

# 輸出結果
for rank, res in enumerate(results):
    name = res['name'].replace(".vsp3", "")
    print(f"{name:<25} | {res['area']:<12.4f} | {res['drag']:<15.5f} | No. {rank+1}")

print("-" * 75)
print("💡 結論：")
print("請比較 'Type_B_HighSpeed' (細長) 與 'Type_C_Comfort' (短胖) 的阻力差距。")
print(f"在 {V} m/s 的速度下，每一個牛頓 (N) 都代表飛行員要多輸出的功率。")