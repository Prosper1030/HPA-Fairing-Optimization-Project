"""驗證 Z 偏移方案的效果"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp

# 測試基因
gene = {
    'L': 2.5,
    'W_max': 0.60,
    'H_top_max': 0.95,
    'H_bot_max': 0.35,
}

print("="*60)
print("驗證 Z 偏移方案")
print("="*60)

# 計算期望值
H_total = gene['H_top_max'] + gene['H_bot_max']
Delta_Z = (gene['H_top_max'] - gene['H_bot_max']) / 2.0

print(f"\n📊 期望值（根據數學公式）:")
print(f"   H_top = {gene['H_top_max']:.3f} m")
print(f"   H_bot = {gene['H_bot_max']:.3f} m")
print(f"   總高度 H_total = {H_total:.3f} m")
print(f"   Z 偏移 Delta_Z = {Delta_Z:.3f} m")

# 驗證公式
print(f"\n🔍 驗證數學公式:")
top_result = H_total/2 + Delta_Z
bot_result = -H_total/2 + Delta_Z
print(f"   頂部 = H_total/2 + Delta_Z = {top_result:.3f} m (期望: {gene['H_top_max']:.3f})")
print(f"   底部 = -H_total/2 + Delta_Z = {bot_result:.3f} m (期望: {-gene['H_bot_max']:.3f})")

if abs(top_result - gene['H_top_max']) < 0.001:
    print(f"   ✅ 頂部公式正確")
else:
    print(f"   ❌ 頂部公式錯誤")

if abs(bot_result - (-gene['H_bot_max'])) < 0.001:
    print(f"   ✅ 底部公式正確")
else:
    print(f"   ❌ 底部公式錯誤")

# 讀取模型檢查實際值
vsp.ClearVSPModel()
vsp_file = "output/test_hpa_fixed_params.vsp3"
vsp.ReadVSPFile(vsp_file)

geoms = vsp.FindGeoms()
fuse_id = geoms[0]

xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
num_xsec = vsp.GetNumXSec(xsec_surf)

print(f"\n📋 VSP 模型中的實際值:")

# 檢查中間截面
target_idx = num_xsec // 2

for i in [target_idx - 1, target_idx, target_idx + 1]:
    if i < 1 or i >= num_xsec - 1:
        continue

    xsec = vsp.GetXSec(xsec_surf, i)

    # 獲取參數
    psi_parm = vsp.GetXSecParm(xsec, "XLocPercent")
    if not psi_parm:
        continue
    psi = vsp.GetParmVal(psi_parm)

    width_parm = vsp.GetXSecParm(xsec, "Super_Width")
    height_parm = vsp.GetXSecParm(xsec, "Super_Height")
    z_offset_parm = vsp.GetXSecParm(xsec, "Z_Offset")

    if width_parm and height_parm and z_offset_parm:
        width = vsp.GetParmVal(width_parm)
        height = vsp.GetParmVal(height_parm)
        z_offset = vsp.GetParmVal(z_offset_parm)

        # 計算頂部和底部位置
        actual_top = height/2 + z_offset
        actual_bot = -height/2 + z_offset

        print(f"\n   截面 {i} (psi={psi:.3f}):")
        print(f"      寬度: {width:.3f} m")
        print(f"      總高度: {height:.3f} m")
        print(f"      Z 偏移: {z_offset:.3f} m")
        print(f"      => 頂部: {actual_top:.3f} m")
        print(f"      => 底部: {actual_bot:.3f} m")

print(f"\n💡 在 VSP GUI 中:")
print(f"   1. 打開 output/test_hpa_fixed_params.vsp3")
print(f"   2. 選擇任一中間截面（例如截面 {target_idx}）")
print(f"   3. 查看 Z_Offset 參數 = {Delta_Z:.3f} m")
print(f"   4. 側視圖應該看到上半部明顯比下半部大")

print("\n" + "="*60)
