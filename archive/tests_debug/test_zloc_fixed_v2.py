"""測試zloc修復（版本2 - 使用新檔名）"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# 強制重新載入模組
if 'optimization.hpa_asymmetric_optimizer' in sys.modules:
    del sys.modules['optimization.hpa_asymmetric_optimizer']

import openvsp as vsp
from optimization.hpa_asymmetric_optimizer import CST_Modeler, VSPModelGenerator

print("="*80)
print("測試ZLoc修復 - 版本2（新檔名）")
print("="*80)

gene = {
    'L': 2.5,
    'W_max': 0.60,
    'H_top_max': 0.95,
    'H_bot_max': 0.35,
    'N1': 0.5,
    'N2_top': 0.7,
    'N2_bot': 0.8,
    'X_max_pos': 0.25,
    'X_offset': 0.7,
}

print(f"\n📊 生成曲線...")
curves = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=40)

print(f"\n📈 關鍵數值檢查:")
print(f"   上邊界範圍: [{min(curves['z_upper']):.3f}, {max(curves['z_upper']):.3f}] m")
print(f"   下邊界範圍: [{min(curves['z_lower']):.3f}, {max(curves['z_lower']):.3f}] m")
print(f"   Z中心範圍: [{min(curves['z_loc']):.3f}, {max(curves['z_loc']):.3f}] m")

# 檢查幾個關鍵截面
print(f"\n🔍 關鍵截面:")
for i in [0, 10, 20, 30, 39]:
    print(f"   截面{i:2d}: z_upper={curves['z_upper'][i]:7.3f}, z_lower={curves['z_lower'][i]:7.3f}, z_loc={curves['z_loc'][i]:7.3f}")

# 生成VSP模型 - 使用新檔名
output_file = "output/fairing_zloc_fixed_v2.vsp3"

print(f"\n🚀 生成VSP模型: {output_file}")
VSPModelGenerator.create_fuselage(
    curves,
    name="Fairing_ZLoc_Fixed_V2",
    filepath=output_file
)

print(f"   ✅ 模型已保存")

# 驗證VSP文件中的值
print(f"\n🔍 驗證VSP文件中的ZLoc值:")
vsp.ClearVSPModel()
vsp.ReadVSPFile(output_file)

geoms = vsp.FindGeoms()
fuse_id = geoms[0]
xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

print(f"{'截面':^6} {'預期z_loc':^12} {'VSP中z_loc':^12} {'差異':^10}")
print("-" * 50)

all_match = True
for i in [0, 10, 20, 30, 39]:
    expected = curves['z_loc'][i]
    xsec = vsp.GetXSec(xsec_surf, i)
    z_parm = vsp.GetXSecParm(xsec, "ZLocPercent")
    actual = vsp.GetParmVal(z_parm) if z_parm else 0.0
    diff = abs(actual - expected)

    status = "✅" if diff < 0.001 else "❌"
    print(f"{i:^6} {expected:^12.3f} {actual:^12.3f} {diff:^10.4f} {status}")

    if diff >= 0.001:
        all_match = False

print("=" * 80)
if all_match:
    print("✅ 所有ZLoc值正確！")
    print(f"\n請在VSP GUI中打開: {output_file}")
    print("應該看到:")
    print("  - 上邊界最高約 0.95m")
    print("  - 下邊界最低約 -0.35m")
    print("  - 機頭和機尾都在 Z=0 附近閉合")
else:
    print("❌ ZLoc值不匹配！")

print("=" * 80)
