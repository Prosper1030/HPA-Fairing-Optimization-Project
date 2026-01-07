"""簡單測試：直接修改curves的z_loc值"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from optimization.hpa_asymmetric_optimizer import CST_Modeler, VSPModelGenerator
import copy

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

print("生成基礎curves...")
curves_base = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=10)  # 用10個截面加快速度

methods = [
    ('absolute', lambda z: z, '絕對值（當前）'),
    ('div_length', lambda z: z / gene['L'], '除以長度'),
    ('zero', lambda z: 0.0, '全部設為0'),
]

for name, transform, desc in methods:
    print(f"\n方法: {desc}")

    curves = copy.deepcopy(curves_base)
    curves['z_loc'] = [transform(z) for z in curves_base['z_loc']]

    filename = f"output/zloc_test_{name}.vsp3"

    try:
        VSPModelGenerator.create_fuselage(
            curves,
            name=f"ZLoc_Test_{name}",
            filepath=filename
        )
        print(f"   ✅ {filename}")
    except Exception as e:
        print(f"   ❌ 失敗: {e}")

print("\n請在VSP GUI中打開這3個檔案，看哪個位置正確！")
