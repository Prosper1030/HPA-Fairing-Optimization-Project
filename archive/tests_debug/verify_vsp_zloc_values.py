"""驗證VSP文件中的ZLoc值是否正確設置"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp
from optimization.hpa_asymmetric_optimizer import CST_Modeler

# 生成預期的曲線
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

curves = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=40)

print("="*80)
print("驗證VSP文件中的ZLoc值")
print("="*80)

# 讀取VSP文件
vsp_file = "output/test_new_geometry.vsp3"
vsp.ClearVSPModel()
vsp.ReadVSPFile(vsp_file)

geom_ids = vsp.FindGeoms()
if len(geom_ids) == 0:
    print("❌ 沒有找到幾何體")
    sys.exit(1)

fuse_id = geom_ids[0]
xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
num_sections = vsp.GetNumXSec(xsec_surf)

print(f"\n📊 檢查關鍵截面的ZLoc值:")
print("-" * 80)
print(f"{'截面':^6} {'預期z_upper':^12} {'預期z_lower':^12} {'預期z_loc':^12} {'VSP ZLoc':^12} {'差異':^10}")
print("-" * 80)

max_error = 0
for i in [0, 10, 20, 30, 39]:
    if i >= num_sections:
        continue

    # 預期值
    expected_z_upper = curves['z_upper'][i]
    expected_z_lower = curves['z_lower'][i]
    expected_z_loc = curves['z_loc'][i]

    # VSP中的實際值
    xsec = vsp.GetXSec(xsec_surf, i)
    z_loc_parm = vsp.GetXSecParm(xsec, "ZLocPercent")

    if z_loc_parm:
        actual_z_loc = vsp.GetParmVal(z_loc_parm)
    else:
        actual_z_loc = 0.0

    error = abs(actual_z_loc - expected_z_loc)
    max_error = max(max_error, error)

    status = "✅" if error < 0.01 else "❌"
    print(f"{i:^6} {expected_z_upper:^12.3f} {expected_z_lower:^12.3f} {expected_z_loc:^12.3f} {actual_z_loc:^12.3f} {error:^10.4f} {status}")

print("-" * 80)
print(f"\n最大誤差: {max_error:.4f} m")

if max_error > 0.01:
    print("\n❌ ZLoc值設置不正確！")
    print("\n可能的原因:")
    print("1. VSP文件沒有正確保存")
    print("2. ZLocPercent參數沒有被正確設置")
    print("3. 程式碼中有其他地方覆蓋了ZLoc值")
else:
    print("\n✅ ZLoc值設置正確！")
    print("\n如果在VSP GUI中看起來位置不對，可能是:")
    print("1. VSP的顯示問題（嘗試重新打開文件）")
    print("2. ZLocPercent的解釋方式與預期不同")

print("="*80)
