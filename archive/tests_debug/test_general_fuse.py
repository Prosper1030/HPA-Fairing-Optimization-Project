"""測試 XS_GENERAL_FUSE 是否支持上下非對稱"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp

print("="*60)
print("測試 XS_GENERAL_FUSE")
print("="*60)

# 清空模型
vsp.ClearVSPModel()

# 創建 Fuselage
fuse_id = vsp.AddGeom("FUSELAGE")

# 獲取截面表面
xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

# 改變第1個截面為 GENERAL_FUSE
vsp.ChangeXSecShape(xsec_surf, 1, vsp.XS_GENERAL_FUSE)
xsec = vsp.GetXSec(xsec_surf, 1)

print("\n✅ 創建 GENERAL_FUSE 截面成功")

# 獲取所有參數
print("\n📊 GENERAL_FUSE 參數列表:")

# 嘗試獲取常見參數
param_names = [
    "Height", "Width", "MaxWidthLoc", "CornerRad",
    "TopTanAngle", "BotTanAngle", "TopStr", "BotStr",
    "UpStr", "LowStr", "TopLAngle", "TopLStr", "RightLAngle", "RightLStr",
    "Z_Offset", "TopHeight", "BotHeight", "TopLoc", "BotLoc"
]

found_params = {}
for param in param_names:
    try:
        parm_id = vsp.GetXSecParm(xsec, param)
        if parm_id:
            value = vsp.GetParmVal(parm_id)
            found_params[param] = value
            print(f"   ✅ {param:20s} = {value:.4f}")
    except:
        pass

if len(found_params) == 0:
    print("   ⚠️ 未找到參數，嘗試列出所有 Parm...")

    # 嘗試獲取所有 Parm
    parm_container = vsp.FindContainer("XSec", 0)
    if parm_container:
        print(f"   找到容器: {parm_container}")

print("\n" + "="*60)
