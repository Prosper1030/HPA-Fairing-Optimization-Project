#!vsp_env\Scripts\python.exe
# -*- coding: utf-8 -*-
import openvsp as vsp
import math
import sys
import json
import os

# --- 1. CST 數學核心 (不變) ---
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

# --- 2. 建模主程式 (封裝成函數) ---
def build_cst_fuselage(config):
    # 讀取參數
    name = config["name"]
    L = config["length"]
    N_nose = config["n_nose"]
    N_tail = config["n_tail"]
    W_weights = config["width_weights"]
    H_weights = config["height_weights"]

    print(f"\n🔨 正在建造: {name} (長度={L}m)...")

    vsp.ClearVSPModel() 
    fuse_id = vsp.AddGeom("FUSELAGE")
    vsp.SetGeomName(fuse_id, name)
    vsp.SetParmVal(fuse_id, "Length", "Design", L)
    
    xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
    
    # 定量切割 (使用穩定版邏輯)
    target_xsecs = 40
    current_secs = vsp.GetNumXSec(xsec_surf)
    needed_cuts = target_xsecs - current_secs
    
    for i in range(needed_cuts):
        vsp.CutXSec(fuse_id, 1)
        vsp.Update() # 重要！
    
    # 應用形狀
    final_count = vsp.GetNumXSec(xsec_surf)
    for i in range(final_count):
        xsec = vsp.GetXSec(xsec_surf, i)
        psi = i / (final_count - 1)
        
        # 設定位置
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "XLocPercent"), psi)
        
        # 避開機頭機尾的 Point
        if vsp.GetXSecShape(xsec) == 0:
            continue
            
        r_width = calculate_cst_radius(psi, N_nose, N_tail, W_weights, L)
        r_height = calculate_cst_radius(psi, N_nose, N_tail, H_weights, L)
        
        w = max(r_width * 2, 0.001)
        h = max(r_height * 2, 0.001)
        
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Ellipse_Width"), w)
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Ellipse_Height"), h)
            
    vsp.Update()
    
    # 存檔
    filename = f"{name}.vsp3"
    vsp.WriteVSPFile(filename)
    print(f"   ✅ 已儲存: {filename}")

# --- 3. 讀取 JSON 並批次執行 ---
print("🚀 啟動批次生產模式...")

json_file = "designs.json"

if not os.path.exists(json_file):
    print(f"❌ 找不到設定檔: {json_file}")
else:
    with open(json_file, "r", encoding="utf-8") as f:
        designs = json.load(f)
    
    print(f"📄 讀取到 {len(designs)} 個設計案，開始生產！")
    
    for design in designs:
        try:
            build_cst_fuselage(design)
        except Exception as e:
            print(f"❌ 建造 {design['name']} 時發生錯誤: {e}")

print("\n🎉 全部完成！請到資料夾查看 3 個 .vsp3 檔案。")