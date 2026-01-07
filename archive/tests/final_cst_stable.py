import openvsp as vsp
import math
import sys
import time

# --- 1. CST 數學核心 ---
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

# --- 2. 建模主程式 (穩定版) ---
def build_cst_fuselage(length, N_nose, N_tail, weights_width, weights_height):
    print("   [1/4] 清空場景...")
    vsp.ClearVSPModel() 
    
    print("   [2/4] 建立機身...")
    fuse_id = vsp.AddGeom("FUSELAGE")
    vsp.SetGeomName(fuse_id, "CST_Fairing")
    vsp.SetParmVal(fuse_id, "Length", "Design", length)
    
    xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
    
    # --- 關鍵修改：定量切割 + 強制更新 ---
    target_xsecs = 40
    current_secs = vsp.GetNumXSec(xsec_surf) # 通常是 5
    needed_cuts = target_xsecs - current_secs
    
    print(f"   [3/4] 目前 {current_secs} 段，準備執行 {needed_cuts} 次切割...")
    
    # 我們改用 for 迴圈，保證只跑這麼多次，絕對不會死結
    for i in range(needed_cuts):
        # 1. 切第 1 段 (避開第 0 段的 Point，切第 1 段的 Ellipse 最安全)
        vsp.CutXSec(fuse_id, 1)
        
        # 2. 強制更新 (這是之前卡住的原因！)
        vsp.Update()
        
        # 3. 顯示進度
        sys.stdout.write(f"\r      -> 進度: {i+1}/{needed_cuts}")
        sys.stdout.flush()
        
    print("\n      -> 切割完成。")

    # --- 應用 CST 參數 ---
    print("   [4/4] 應用 CST 幾何形狀...")
    
    # 重新讀取最終數量
    final_count = vsp.GetNumXSec(xsec_surf)
    
    for i in range(final_count):
        xsec = vsp.GetXSec(xsec_surf, i)
        psi = i / (final_count - 1)
        
        # 設定位置
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "XLocPercent"), psi)
        
        # 判斷形狀類型 (0=Point, 2=Ellipse)
        shape_type = vsp.GetXSecShape(xsec)
        
        # 遇到 Point (機頭/機尾) 就跳過
        if shape_type == 0:
            continue
            
        # 計算 CST
        r_width = calculate_cst_radius(psi, N_nose, N_tail, weights_width, length)
        r_height = calculate_cst_radius(psi, N_nose, N_tail, weights_height, length)
        
        w = max(r_width * 2, 0.001)
        h = max(r_height * 2, 0.001)
        
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Ellipse_Width"), w)
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Ellipse_Height"), h)
            
    vsp.Update()
    return fuse_id

# --- 3. 執行 ---
print("🚀 啟動 Stable CST 程式...")
L = 2.5                 
N_nose = 0.5            
N_tail = 1.0            
W_weights = [0.15, 0.20, 0.20, 0.05] 
H_weights = [0.20, 0.35, 0.25, 0.05] 

try:
    build_cst_fuselage(L, N_nose, N_tail, W_weights, H_weights)
    filename = "Birdman_Fairing_Stable.vsp3"
    vsp.WriteVSPFile(filename)
    print(f"\n\n✅ 成功！機身已儲存為: {filename}")
    print(f"👉 快去打開 OpenVSP，你的飛機終於誕生了！")
except Exception as e:
    import traceback
    print(f"\n❌ 發生錯誤: {e}")
    traceback.print_exc()