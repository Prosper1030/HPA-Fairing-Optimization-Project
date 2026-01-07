import openvsp as vsp
import math
import sys

# --- 1. CST 數學核心 (保持不變) ---
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

# --- 2. 建模主程式 (修復版) ---
def build_cst_fuselage(length, N_nose, N_tail, weights_width, weights_height):
    print("   [1/5] 清空場景...")
    vsp.ClearVSPModel() 
    
    print("   [2/5] 建立機身並初始化...")
    fuse_id = vsp.AddGeom("FUSELAGE")
    vsp.SetGeomName(fuse_id, "CST_Fairing")
    vsp.SetParmVal(fuse_id, "Length", "Design", length)
    
    # 取得截面管理器
    xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
    
    # --- 關鍵修正：強制轉型 ---
    # 預設的機身頭尾是「點(Point)」，無法設定寬高。
    # 我們必須先把它們轉成「橢圓(Ellipse)」，才能用 CST 控制。
    print("   [3/5] 強制轉換截面類型為橢圓...")
    
    # 先讀取目前的數量 (通常是 5 個: Point-Ellipse-Ellipse-Ellipse-Point)
    num_init = vsp.GetNumXSec(xsec_surf)
    for i in range(num_init):
        # XS_ELLIPSE 的代碼通常是 2
        vsp.SetXSecShape(vsp.GetXSec(xsec_surf, i), vsp.XS_ELLIPSE)

    # --- 切割截面 ---
    target_xsecs = 40
    print(f"   [4/5] 正在切分截面至 {target_xsecs} 段...")
    
    current_secs = vsp.GetNumXSec(xsec_surf)
    while current_secs < target_xsecs:
        # 永遠切第 0 段，最安全
        vsp.CutXSec(fuse_id, 0)
        current_secs = vsp.GetNumXSec(xsec_surf)
        
    print(f"      -> 切割完成，目前共有 {current_secs} 個截面。")

    # --- 應用 CST 參數 ---
    print("   [5/5] 應用 CST 幾何形狀...")
    
    for i in range(current_secs):
        xsec = vsp.GetXSec(xsec_surf, i)
        
        # 計算相對位置 psi (0 ~ 1)
        psi = i / (current_secs - 1)
        
        # 1. 設定位置 (修正：使用 XLocPercent)
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "XLocPercent"), psi)
        
        # 2. CST 計算半徑
        r_width = calculate_cst_radius(psi, N_nose, N_tail, weights_width, length)
        r_height = calculate_cst_radius(psi, N_nose, N_tail, weights_height, length)
        
        # 3. 寫入寬高
        # 即使是頭尾，因為已經轉成橢圓了，這裡設極小值也不會報錯
        w = max(r_width * 2, 0.001)
        h = max(r_height * 2, 0.001)
        
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Ellipse_Width"), w)
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Ellipse_Height"), h)
            
    vsp.Update()
    return fuse_id

# --- 3. 執行 ---
print("🚀 啟動最終修復版程式...")
L = 2.5                 
N_nose = 0.5            
N_tail = 1.0            
W_weights = [0.15, 0.20, 0.20, 0.05] 
H_weights = [0.20, 0.35, 0.25, 0.05] 

try:
    build_cst_fuselage(L, N_nose, N_tail, W_weights, H_weights)
    filename = "Birdman_Fairing_Final.vsp3"
    vsp.WriteVSPFile(filename)
    print(f"\n\n✅ 完美成功！機身已儲存為: {filename}")
    print(f"👉 請立刻用 OpenVSP 打開這個檔案，欣賞你的 CST 傑作！")
except Exception as e:
    print(f"\n❌ 還是有錯 (不應該發生): {e}")