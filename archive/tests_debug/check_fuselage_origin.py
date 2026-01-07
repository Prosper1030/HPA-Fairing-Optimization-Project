"""檢查Fuselage物件的原點和偏移參數"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp

print("="*80)
print("檢查Fuselage物件級別的位置參數")
print("="*80)

# 創建一個簡單的fuselage來檢查可用參數
vsp.ClearVSPModel()
fuse_id = vsp.AddGeom("FUSELAGE")

print("\n🔍 搜尋Fuselage的位置相關參數:")
print("-" * 60)

# 可能的參數名稱
possible_params = [
    "X_Rel_Location", "Y_Rel_Location", "Z_Rel_Location",
    "X_Location", "Y_Location", "Z_Location",
    "XLoc", "YLoc", "ZLoc",
    "X_Offset", "Y_Offset", "Z_Offset",
    "Origin_X", "Origin_Y", "Origin_Z",
    "Abs_Or_Relitive_flag",
]

for param_name in possible_params:
    parm = vsp.FindParm(fuse_id, param_name, "XForm")
    if parm:
        value = vsp.GetParmVal(parm)
        print(f"   ✅ {param_name}: {value:.6f}")
    else:
        # 也試試其他group
        parm = vsp.FindParm(fuse_id, param_name, "Design")
        if parm:
            value = vsp.GetParmVal(parm)
            print(f"   ✅ {param_name} (Design): {value:.6f}")

print("-" * 60)

# 檢查Example.vsp3的fuselage設定
print("\n📊 檢查Example.vsp3的Fuselage位置:")
vsp.ClearVSPModel()
vsp.ReadVSPFile("output/current/Example.vsp3")

geoms = vsp.FindGeoms()
if geoms:
    fuse_id = geoms[0]

    for param_name in ["X_Rel_Location", "Y_Rel_Location", "Z_Rel_Location"]:
        parm = vsp.FindParm(fuse_id, param_name, "XForm")
        if parm:
            value = vsp.GetParmVal(parm)
            print(f"   {param_name}: {value:.6f}")

print("\n" + "="*80)
print("💡 如果Z_Rel_Location不是0，那可能需要調整整個Fuselage的Z位置！")
print("="*80)
