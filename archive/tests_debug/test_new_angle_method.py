"""測試新的角度計算方法 - 直接從z_upper/z_lower斜率計算"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# 強制重新載入
if 'optimization.hpa_asymmetric_optimizer' in sys.modules:
    del sys.modules['optimization.hpa_asymmetric_optimizer']
if 'math.cst_derivatives' in sys.modules:
    del sys.modules['math.cst_derivatives']

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
print("測試新角度計算方法")
print("="*80)
print("✅ 直接從z_upper和z_lower曲線計算斜率")
print("✅ 不再使用CST導數（那是為對稱幾何設計的）")
print("="*80)

curves = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=40)

output_file = "output/fairing_new_angle_method.vsp3"
print(f"\n生成: {output_file}")

VSPModelGenerator.create_fuselage(
    curves,
    name="Fairing_New_Angle_Method",
    filepath=output_file
)

print(f"✅ 完成！")
print(f"\n請在VSP GUI中檢查skinning是否明顯改善")
print("  特別注意：上半部和下半部後段")
print("="*80)
