"""測試完整角度修復 - Bottom正負號 + Nose/Tail新方法"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# 強制重新載入
for module in ['optimization.hpa_asymmetric_optimizer', 'math.cst_derivatives']:
    if module in sys.modules:
        del sys.modules[module]

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
print("測試完整角度修復")
print("="*80)
print("✅ Bottom角度加入負號修正")
print("✅ Nose/Tail使用新的非對稱角度計算法")
print("✅ 所有截面使用統一的角度計算方法")
print("="*80)

curves = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=40)

output_file = "output/current/fairing_complete_angle_fix.vsp3"
print(f"\n生成: {output_file}")

VSPModelGenerator.create_fuselage(
    curves,
    name="Fairing_Complete_Fix",
    filepath=output_file
)

print(f"✅ 完成！")
print(f"\n請在VSP GUI中檢查:")
print("  1. Top表面：應該完全平滑（包括機頭機尾）")
print("  2. Bottom表面：應該完全平滑（包括機頭機尾）")
print("  3. 下邊界：約-0.35m位置")
print("="*80)
