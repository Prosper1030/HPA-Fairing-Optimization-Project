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
    # 如果在邊界，直接回傳 0，避免數學誤差
    if psi <= 0 or psi >= 1: return 0.0
    C = cst_class_function(psi, N1, N2)
    S = cst_shape_function(psi, weights)
    return C * S * length

# --- 2. 建模主程式 (智慧版) ---
def build_cst_fuselage(length, N_nose, N_tail, weights_width, weights_height):
    print("   [1/4] 清空場景...")
    vsp.ClearVSPModel() 
    
    print("   [2/4] 建立機身...")
    fuse_id = vsp.AddGeom("FUSELAGE")
    vsp.SetGeomName(fuse_id, "CST_Fairing")
    vsp.SetParmVal(fuse_id, "Length", "Design", length)
    
    xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
    
    # --- 切割截面 ---
    target_xsecs = 40
    print(f"   [3/4] 正在切分截面至 {target_xsecs} 段...")
    
    current_secs = vsp.GetNumXSec(xsec_surf)
    while current_secs < target_xsecs:
        # 切第 0 段最安全
        vsp.CutXSec(fuse_id, 0)
        current_secs = vsp.GetNumXSec(xsec_surf)

    # --- 應用 CST 參數 (智慧判斷) ---
    print("   [4/4] 應用 CST 幾何形狀...")
    
    for i in range(current_secs):
        xsec = vsp.GetXSec(xsec_surf, i)
        
        # 1. 計算相對位置 psi (0 ~ 1)
        psi = i / (current_secs - 1)
        
        # 2. 設定 X 位置 (使用診斷出來的正確名稱 XLocPercent)
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "XLocPercent"), psi)
        
        # 3. 檢查截面類型
        # 0 = Point (點), 2 = Ellipse (橢圓)
        shape_type = vsp.GetXSecShape(xsec)
        
        if shape_type == 0:
            # 如果是「點」，我們只設位置，不設寬高 (因為它沒有寬高參數)
            # 這通常是機頭或機尾，半徑本來就是 0
            continue 
            
        # 4. 如果是「橢圓」，才計算並設定 CST 寬高
        r_width = calculate_cst_radius(psi, N_nose, N_tail, weights_width, length)
        r_height = calculate_cst_radius(psi, N_nose, N_tail, weights_height, length)
        
        # 寫入 (給一個極小值防呆)
        w = max(r_width * 2, 0.001)
        h = max(r_height * 2, 0.001)
        
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Ellipse_Width"), w)
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Ellipse_Height"), h)
            
    vsp.Update()
    return fuse_id

# --- 3. 執行 ---
print("🚀 啟動 Smart CST 程式...")
L = 2.5                 
N_nose = 0.5            
N_tail = 1.0            
W_weights = [0.15, 0.20, 0.20, 0.05] 
H_weights = [0.20, 0.35, 0.25, 0.05] 

try:
    build_cst_fuselage(L, N_nose, N_tail, W_weights, H_weights)
    filename = "Birdman_Fairing.vsp3"
    vsp.WriteVSPFile(filename)
    print(f"\n\n✅ 成功！機身已儲存為: {filename}")
    print(f"👉 請打開 OpenVSP 查看。這次參數錯誤已被完美繞過！")
except Exception as e:
    import traceback
    print(f"\n❌ 發生錯誤: {e}")
    traceback.print_exc()