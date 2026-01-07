import openvsp as vsp
import math

# --- 1. CST 數學核心 (Class-Shape Transformation) ---
def cst_class_function(psi, N1, N2):
    return (psi ** N1) * ((1 - psi) ** N2)

def cst_shape_function(psi, weights):
    n = len(weights) - 1
    S = 0
    for i in range(len(weights)):
        # 計算組合數 (n choose i)
        comb = math.factorial(n) / (math.factorial(i) * math.factorial(n - i))
        bernstein = comb * (psi ** i) * ((1 - psi) ** (n - i))
        S += weights[i] * bernstein
    return S

def calculate_cst_radius(psi, N1, N2, weights, length):
    if psi <= 0 or psi >= 1: return 0.0
    C = cst_class_function(psi, N1, N2)
    S = cst_shape_function(psi, weights)
    return C * S * length

# --- 2. 建模主程式 ---
def build_cst_fuselage(length, N_nose, N_tail, weights_width, weights_height):
    # 清空場景 (避免重複疊加)
    vsp.ClearVSPModel() 
    
    # 新增機身幾何
    fuse_id = vsp.AddGeom("FUSELAGE")
    vsp.SetGeomName(fuse_id, "CST_Fairing")
    vsp.SetParmVal(fuse_id, "Length", "Design", length)
    
    # 設定切分段數 (越多越平滑)
    num_xsecs = 40
    
    # 初始化截面
    xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
    vsp.CutXSec(fuse_id, 0) 
    
    # 補足截面數量
    while vsp.GetNumXSec(xsec_surf) < num_xsecs:
        vsp.CutXSec(fuse_id, 1)
    
    # --- 逐一設定每個截面 (從頭到尾) ---
    for i in range(num_xsecs):
        xsec = vsp.GetXSec(xsec_surf, i)
        psi = i / (num_xsecs - 1) # 相對位置 (0~1)
        
        # 設定 X 位置
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "X_Loc"), psi)
        
        # CST 計算半徑
        r_width = calculate_cst_radius(psi, N_nose, N_tail, weights_width, length)
        r_height = calculate_cst_radius(psi, N_nose, N_tail, weights_height, length)
        
        # 寫入 VSP (Width/Height 是直徑，所以 * 2)
        # 防呆：給一個極小值 0.001 避免 VSP 報錯
        w = max(r_width * 2, 0.001)
        h = max(r_height * 2, 0.001)
        
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Ellipse_Width"), w)
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Ellipse_Height"), h)
        
    vsp.Update()
    return fuse_id

# --- 3. 執行參數設定 (鳥人間比賽用) ---
print("🚀 正在生成高性能整流罩...")

# 參數設定
L = 2.5                 # 機身長度 (m)
N_nose = 0.5            # 圓頭 (0.5 = 橢圓)
N_tail = 1.0            # 尖尾 (1.0 = 錐狀)
W_weights = [0.15, 0.20, 0.20, 0.05] # 寬度分佈
H_weights = [0.20, 0.35, 0.25, 0.05] # 高度分佈

build_cst_fuselage(L, N_nose, N_tail, W_weights, H_weights)

# 存檔
filename = "Birdman_Fairing.vsp3"
vsp.WriteVSPFile(filename)
print(f"✅ 成功！機身已儲存為: {filename}")
print(f"請用 OpenVSP 開啟此檔案檢查形狀。")