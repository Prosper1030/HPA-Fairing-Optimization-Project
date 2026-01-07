"""分析範例VSP文件的Z位置設置"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp

print("="*60)
print("分析範例VSP文件的Z位置設置")
print("="*60)

# 讀取範例文件
vsp.ClearVSPModel()
vsp_file = "output/Example.vsp3"
vsp.ReadVSPFile(vsp_file)

geoms = vsp.FindGeoms()
if not geoms:
    print("❌ 沒有找到幾何體")
    sys.exit(1)

fuse_id = geoms[0]
print(f"\n📋 幾何體 ID: {fuse_id}")
print(f"   名稱: {vsp.GetGeomName(fuse_id)}")

# 獲取截面信息
xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
num_xsec = vsp.GetNumXSec(xsec_surf)

print(f"\n📊 截面數量: {num_xsec}")

print(f"\n🔍 分析每個截面的Z位置參數:")

for i in range(num_xsec):
    xsec = vsp.GetXSec(xsec_surf, i)

    # 獲取截面類型
    shape_type = vsp.GetXSecShape(xsec)
    type_names = {
        vsp.XS_POINT: "POINT",
        vsp.XS_SUPER_ELLIPSE: "SUPER_ELLIPSE",
        vsp.XS_CIRCLE: "CIRCLE",
        vsp.XS_ELLIPSE: "ELLIPSE",
        vsp.XS_FILE_FUSE: "FILE_FUSE"
    }
    type_name = type_names.get(shape_type, f"UNKNOWN({shape_type})")

    # 獲取X位置
    x_loc_parm = vsp.GetXSecParm(xsec, "XLocPercent")
    x_loc = vsp.GetParmVal(x_loc_parm) if x_loc_parm else 0.0

    print(f"\n   截面 {i} ({type_name}), X={x_loc:.3f}:")

    # 嘗試獲取各種Z位置參數
    # 方法1: 直接從XSec參數獲取
    z_params_to_try = [
        "ZLoc", "ZLocPercent", "Z_Offset", "ZOffset", "Z_Location"
    ]

    for param_name in z_params_to_try:
        parm = vsp.GetXSecParm(xsec, param_name)
        if parm:
            value = vsp.GetParmVal(parm)
            print(f"      {param_name}: {value:.6f}")

    # 方法2: 使用FindParm在XSec群組中查找
    group_name = f"XSec_{i}"
    for param_name in ["ZLoc", "ZLocPercent", "AbsRelFlag"]:
        parm = vsp.FindParm(fuse_id, param_name, group_name)
        if parm:
            value = vsp.GetParmVal(parm)
            if param_name == "AbsRelFlag":
                flag_name = "ABS" if value == 0 else "REL"
                print(f"      {group_name}/{param_name}: {flag_name} ({value})")
            else:
                print(f"      {group_name}/{param_name}: {value:.6f}")

    # 獲取截面幾何參數
    if shape_type == vsp.XS_SUPER_ELLIPSE:
        width_parm = vsp.GetXSecParm(xsec, "Super_Width")
        height_parm = vsp.GetXSecParm(xsec, "Super_Height")
        if width_parm and height_parm:
            width = vsp.GetParmVal(width_parm)
            height = vsp.GetParmVal(height_parm)
            print(f"      Width: {width:.3f}, Height: {height:.3f}")

print("\n" + "="*60)
print("分析完成！")
print("="*60)
