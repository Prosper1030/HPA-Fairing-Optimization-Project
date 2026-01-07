"""生成最終版本 - ZLoc修復 + Skinning修復 + Strength調整"""
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
print("生成最終版本")
print("="*80)
print("✅ ZLocPercent歸一化（除以Length）")
print("✅ 對稱截面使用統一角度")
print("✅ Strength變動調整（前0.6, 中0.85, 後1.1）")
print("="*80)

curves = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=40)

output_file = "output/fairing_final_v1.vsp3"
print(f"\n生成: {output_file}")

VSPModelGenerator.create_fuselage(
    curves,
    name="Fairing_Final_V1",
    filepath=output_file
)

print(f"✅ 完成！")
print(f"\n請在VSP GUI中檢查:")
print("  1. 位置：下邊界約-0.35m")
print("  2. Skinning：特別檢查上半部和下半部後段")
print("="*80)
