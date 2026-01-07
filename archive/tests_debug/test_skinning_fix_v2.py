"""測試Skinning修復 v2 - 新檔案"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# 強制重新載入
if 'optimization.hpa_asymmetric_optimizer' in sys.modules:
    del sys.modules['optimization.hpa_asymmetric_optimizer']

from optimization.hpa_asymmetric_optimizer import CST_Modeler, VSPModelGenerator

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

print("="*80)
print("生成帶有Skinning修復的模型")
print("="*80)

curves = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=40)

# 檢查對稱性
print("\n檢查哪些截面是對稱的:")
for i in [0, 10, 20, 30, 38, 39]:
    z_u = curves['z_upper'][i]
    z_l = curves['z_lower'][i]
    is_sym = abs(z_u - z_l) < 0.02
    print(f"   截面{i}: z_upper={z_u:.3f}, z_lower={z_l:.3f}, 對稱={is_sym}")

# 生成VSP模型
output_file = "output/fairing_skinning_fix_v2.vsp3"
print(f"\n生成模型: {output_file}")

VSPModelGenerator.create_fuselage(
    curves,
    name="Fairing_Skinning_Fix_V2",
    filepath=output_file
)

print(f"✅ 模型已保存")
print(f"\n請在VSP GUI中檢查skinning是否平滑")
print("="*80)
