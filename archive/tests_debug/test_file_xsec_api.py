"""測試 VSP File XSec API"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp
import numpy as np

print("="*60)
print("測試 VSP File XSec API")
print("="*60)

# 清空模型
vsp.ClearVSPModel()

# 創建 Fuselage
fuse_id = vsp.AddGeom("FUSELAGE")
vsp.SetGeomName(fuse_id, "TestFuse")

# 獲取截面表面
xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

# 添加一個截面
vsp.InsertXSec(fuse_id, 1, vsp.XS_FILE_FUSE)
vsp.Update()

# 改變第1個截面為 FILE_FUSE
vsp.ChangeXSecShape(xsec_surf, 1, vsp.XS_FILE_FUSE)
xsec = vsp.GetXSec(xsec_surf, 1)

print("\n✅ 創建 FILE_FUSE 截面成功")

# 生成簡單的圓形截面點
n_points = 20
radius = 0.5
points = []

for i in range(n_points):
    theta = 2 * np.pi * i / n_points
    y = radius * np.cos(theta)
    z = radius * np.sin(theta)
    points.append([0.0, y, z])

print(f"\n📊 生成 {n_points} 個點")
print(f"   範例點: {points[0]}, {points[5]}, {points[10]}")

# 嘗試方法 1: 使用 vec3d list（參考官方示例）
try:
    print("\n方法 1: 使用 vec3d list...")
    pnt_vec = []
    for pt in points:
        pnt_vec.append(vsp.vec3d(pt[0], pt[1], pt[2]))

    print(f"   vec3d list 長度: {len(pnt_vec)}")
    print(f"   第一個點: {pnt_vec[0]}")
    print(f"   xsec ID: {xsec}")

    # 嘗試設置點
    result = vsp.SetXSecPnts(xsec, pnt_vec)
    print(f"   SetXSecPnts 結果: {result}")

    vsp.Update()
    print("   ✅ vec3d list 方法成功!")

except Exception as e:
    print(f"   ❌ vec3d list 方法失敗: {e}")
    import traceback
    traceback.print_exc()

# 嘗試保存
try:
    output_file = "output/test_file_xsec.vsp3"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    vsp.WriteVSPFile(output_file)
    print(f"\n✅ 檔案保存成功: {output_file}")
except Exception as e:
    print(f"\n❌ 檔案保存失敗: {e}")

print("\n" + "="*60)
