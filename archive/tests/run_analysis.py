import openvsp as vsp
import os
import math

# --- 1. 物理環境設定 (25度C, 標準大氣) ---
def get_atmosphere_properties(temp_c):
    # 基礎常數
    T0 = 273.15 + temp_c       # 絕對溫度 (K)
    P0 = 101325.0              # 標準大氣壓 (Pa)
    R = 287.05                 # 氣體常數
    
    # 1. 計算密度 (Rho) [kg/m^3]
    # 理想氣體方程式 P = rho * R * T
    rho = P0 / (R * T0)
    
    # 2. 計算動態黏滯係數 (Dynamic Viscosity, mu) [kg/(m*s)]
    # 使用 Sutherland 公式
    # mu_ref = 1.716e-5, T_ref = 273.15 K, S = 110.4
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
    
    # 取得幾何 ID (假設只有一個機身)
    geoms = vsp.FindGeoms()
    fuse_id = geoms[0]
    
    # --- 重要：執行幾何分析以取得「濕面積 (Wetted Area)」 ---
    # Parasite Drag 需要知道物體表面積才能算摩擦力
    vsp.ComputeGeom(vsp.SET_ALL, vsp.MEASURE_WETTED_AREA)
    
    # --- 設定 Parasite Drag 分析工具 ---
    analysis_name = "Parasite Drag"
    
    # 建立分析設定
    aid = vsp.FindAnalysis(analysis_name)
    vsp.SetAnalysisInputDefaults(aid)
    
    # 設定流體條件
    vsp.SetDoubleAnalysisInput(aid, "Rho", [0], rho)
    vsp.SetDoubleAnalysisInput(aid, "V_inf", [0], velocity)
    vsp.SetDoubleAnalysisInput(aid, "Mu", [0], mu) # 設定黏滯係數讓它算雷諾數
    
    # 執行分析
    vsp.ExecAnalysis(aid)
    
    # --- 讀取結果 ---
    # OpenVSP 的 Parasite Drag 會算出總 CD (以 S_ref 為基準)
    # 我們需要抓出 CD_tot 以及 S_ref 來還原真實阻力
    
    # 取得結果 ID
    res_id = vsp.GetDataNames(aid) # 這只是查看用
    
    # 讀取計算出的總寄生阻力係數 (CDo_Tot)
    # 注意：不同版本 VSP 的變數名稱可能略有不同，通常是 "Tot_CDo"
    cd_total = vsp.GetDoubleAnalysisData(aid, "Tot_CDo", [0])
    
    # 讀取參考面積 (S_ref)
    # OpenVSP 通常用幾何投影面積或濕面積當參考，我們要確認是哪一個
    # 在 Parasite Drag 中，它會輸出 "Tot_Wet_Area"
    s_wet = vsp.GetDoubleAnalysisData(aid, "Tot_Wet_Area", [0])
    
    # 讀取當下的參考面積 (Sref)
    s_ref = vsp.GetDoubleAnalysisData(aid, "Sref", [0])
    
    # --- 計算真實阻力 (Drag Force) ---
    # D = 0.5 * rho * V^2 * S_ref * Cd
    q = 0.5 * rho * (velocity ** 2) # 動壓
    drag_force = q * s_ref * cd_total
    
    return drag_force, s_wet, cd_total

# --- 3. 批次執行 ---
print("🚀 開始空氣動力阻力分析...")
print("---------------------------------------------------------------")
print(f"環境條件: 25°C, 標準大氣壓")

# 設定速度
V = 6.5 # m/s

# 取得環境參數
rho, mu = get_atmosphere_properties(25.0)
print(f"空氣密度 (Rho): {rho:.4f} kg/m^3")
print(f"黏滯係數 (Mu) : {mu:.4e} kg/(m*s)")
print(f"飛行速度 (V)  : {V} m/s")
print(f"雷諾數 (Re/m) : {rho * V / mu:.2e} /m")
print("---------------------------------------------------------------")
print(f"{'設計名稱':<25} | {'濕面積 (m^2)':<12} | {'阻力 (Newton)':<15} | {'省力排名'}")
print("-" * 70)

# 搜尋資料夾內所有的 vsp3 檔案
files = [f for f in os.listdir(".") if f.endswith(".vsp3") and "Birdman" not in f]
# 如果你想包含之前的 debug 檔，就把 "Birdman" 過濾拿掉，或是指定讀取剛剛那三個
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
            print(f"❌ 分析 {filename} 時發生錯誤: {e}")
    else:
        print(f"⚠️ 找不到檔案: {filename}")

# 排序 (阻力由小到大)
results.sort(key=lambda x: x["drag"])

# 輸出結果
for rank, res in enumerate(results):
    name = res['name'].replace(".vsp3", "")
    print(f"{name:<25} | {res['area']:<12.4f} | {res['drag']:<15.5f} | No. {rank+1}")

print("-" * 70)
print("💡 分析建議：")
print("1. 阻力越小越好 (Newton)。")
print("2. 濕面積 (Surface Area) 越小，通常摩擦阻力越小。")
print("3. 這只是估算值，實際情況會受表面粗糙度(製作工藝)影響。")