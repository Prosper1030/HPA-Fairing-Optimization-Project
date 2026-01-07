"""驗證VSP文件中實際設置的skinning角度"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp

print("="*80)
print("驗證VSP文件中的Skinning角度")
print("="*80)

vsp.ClearVSPModel()
vsp.ReadVSPFile("output/fairing_skinning_fix_v2.vsp3")

geoms = vsp.FindGeoms()
fuse_id = geoms[0]
xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

print(f"\n檢查關鍵截面的切線角度:")
print("-" * 80)
print(f"{'截面':^6} {'角度上':^10} {'角度下':^10} {'差異':^10} {'狀態':^8}")
print("-" * 80)

for i in [0, 10, 20, 30, 38, 39]:
    if i >= vsp.GetNumXSec(xsec_surf):
        continue

    xsec = vsp.GetXSec(xsec_surf, i)

    # 獲取切線角度
    angles = vsp.GetXSecTanAngles(xsec, vsp.XSEC_BOTH_SIDES)

    if len(angles) >= 4:
        angle_top = angles[0]     # top
        angle_right = angles[1]   # right
        angle_bot = angles[2]     # bottom
        angle_left = angles[3]    # left

        diff = abs(angle_top - angle_bot)
        status = "✅" if diff < 0.5 else "❌"

        print(f"{i:^6} {angle_top:^10.1f} {angle_bot:^10.1f} {diff:^10.2f} {status:^8}")

print("-" * 80)
print("\n✅ 對稱截面（0, 38, 39）的上下角度應該相同（差異<0.5°）")
print("="*80)
