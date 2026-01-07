import openvsp as vsp
import math
import sys
import time

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

# --- 2. 建模主程式 (偵錯版) ---
def build_cst_fuselage_debug(length, N_nose, N_tail, weights_width, weights_height):
    print("\n[步驟 1] 清空場景...")
    vsp.ClearVSPModel() 
    
    print("[步驟 2] 建立機身物件...")
    fuse_id = vsp.AddGeom("FUSELAGE")
    vsp.SetGeomName(fuse_id, "CST_Fairing")
    vsp.SetParmVal(fuse_id, "Length", "Design", length)
    
    # 檢查初始狀態
    xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
    current_secs = vsp.GetNumXSec(xsec_surf)
    print(f"   -> 初始截面數量: {current_secs}")

    # 目標數量
    target_xsecs = 40
    print(f"[步驟 3] 開始切分截面 (目標: {target_xsecs} 個)...")

    # --- 防死結迴圈 ---
    safety_counter = 0
    max_attempts = 100  # 最多試 100 次，超過就報錯
    
    while current_secs < target_xsecs:
        safety_counter += 1
        
        # 顯示進度
        sys.stdout.write(f"\r   -> 嘗試第 {safety_counter} 次切割 | 目前數量: {current_secs}")
        sys.stdout.flush()

        if safety_counter > max_attempts:
            print("\n\n❌ [錯誤] 偵測到無窮迴圈！")
            print("   原因：CutXSec 指令似乎沒有成功增加截面數量。")
            print("   解決方案：強制停止，嘗試使用現有截面繼續。")
            break

        # 核心動作：嘗試切分
        # 注意：我們切第 1 個索引位置 (如果只有2個截面，切中間)
        # 如果失敗，嘗試改成切 0 看看
        try:
            # 修改策略：永遠切第 0 個，這樣最安全，保證有東西切
            vsp.CutXSec(fuse_id, 0)
        except Exception as e:
            print(f"\n   [VSP報錯] {e}")
            break
            
        # 更新數量
        current_secs = vsp.GetNumXSec(xsec_surf)

    print(f"\n[步驟 3 完成] 最終截面數量: {current_secs}")

    print("[步驟 4] 計算 CST 形狀並寫入參數...")
    for i in range(current_secs):
        # 顯示進度點
        if i % 5 == 0:
            sys.stdout.write(".")
            sys.stdout.flush()

        xsec = vsp.GetXSec(xsec_surf, i)
        psi = i / (current_secs - 1) if current_secs > 1 else 0
        
        # 設定 X 位置
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "X_Loc"), psi)
        
        # CST 計算
        r_width = calculate_cst_radius(psi, N_nose, N_tail, weights_width, length)
        r_height = calculate_cst_radius(psi, N_nose, N_tail, weights_height, length)
        
        # 寫入 (避免 0)
        w = max(r_width * 2, 0.001)
        h = max(r_height * 2, 0.001)
        
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Ellipse_Width"), w)
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Ellipse_Height"), h)
        
    vsp.Update()
    return fuse_id

# --- 3. 執行 ---
print("🚀 開始執行 CST 建模程式 (Debug Mode)...")
L = 2.5                 
N_nose = 0.5            
N_tail = 1.0            
W_weights = [0.15, 0.20, 0.20, 0.05] 
H_weights = [0.20, 0.35, 0.25, 0.05] 

try:
    build_cst_fuselage_debug(L, N_nose, N_tail, W_weights, H_weights)
    filename = "Birdman_Fairing_Debug.vsp3"
    vsp.WriteVSPFile(filename)
    print(f"\n\n✅ 成功！檔案已儲存為: {filename}")
    print(f"👉 請打開 OpenVSP 查看結果。")
except Exception as e:
    print(f"\n❌ 發生未預期的錯誤: {e}")