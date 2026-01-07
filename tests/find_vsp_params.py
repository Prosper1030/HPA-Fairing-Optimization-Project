"""找出 VSP SuperEllipse 截面的所有參數名稱"""
import openvsp as vsp

# 清空並創建測試模型
vsp.ClearVSPModel()
fuse_id = vsp.AddGeom("FUSELAGE")

# 獲取截面表面
xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

# 改變第一個截面為 SuperEllipse
vsp.ChangeXSecShape(xsec_surf, 1, vsp.XS_SUPER_ELLIPSE)
xsec = vsp.GetXSec(xsec_surf, 1)

print("="*60)
print("VSP SuperEllipse 截面參數列表")
print("="*60)

# 獲取所有參數
parm_ids = vsp.GetXSecParmIDs(xsec)

for parm_id in parm_ids:
    if parm_id:
        name = vsp.GetParmName(parm_id)
        val = vsp.GetParmVal(parm_id)
        print(f"  {name}: {val}")

print("="*60)
