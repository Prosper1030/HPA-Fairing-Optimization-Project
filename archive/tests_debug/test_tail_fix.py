"""測試尾部單調收斂修復"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# 強制重新載入
for module in ['optimization.hpa_asymmetric_optimizer', 'math.cst_derivatives']:
    if module in sys.modules:
        del sys.modules[module]

from optimization.hpa_asymmetric_optimizer import CST_Modeler, VSPModelGenerator, CSTDerivatives

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
print("測試尾部單調收斂修復")
print("="*80)
print("✅ 確保上下曲線單調收斂到 tail_rise，避免拐點")
print("✅ 防止 z_upper 下降後再上升（造成扭曲）")
print("="*80)

curves = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=40)

# 檢查尾部曲線是否單調
print("\n尾部曲線檢查（最後10個截面）：")
print(f"{'截面':<6} {'psi':<8} {'z_upper':<10} {'z_lower':<10} {'Top角':<10} {'Bot角':<10}")
print("-"*70)

for i in range(30, 40):
    psi = curves['psi'][i]
    z_upper = curves['z_upper'][i]
    z_lower = curves['z_lower'][i]

    if i < 39:
        angles = CSTDerivatives.compute_asymmetric_tangent_angles(
            curves['x'], curves['z_upper'], curves['z_lower'], i
        )
        angle_top = f"{angles['top']:.2f}"
        angle_bot = f"{angles['bottom']:.2f}"
    else:
        angle_top = angle_bot = "Point"

    print(f"{i:<6} {psi:<8.4f} {z_upper:<10.4f} {z_lower:<10.4f} {angle_top:<10} {angle_bot:<10}")

# 檢查單調性
print("\n單調性檢查：")
monotonic_upper = True
monotonic_lower = True
for i in range(31, 39):
    if curves['z_upper'][i] > curves['z_upper'][i-1]:
        print(f"   ⚠️ 上曲線在截面{i}處上升（可能造成扭曲）")
        monotonic_upper = False
    if curves['z_lower'][i] < curves['z_lower'][i-1]:
        print(f"   ⚠️ 下曲線在截面{i}處下降（可能造成扭曲）")
        monotonic_lower = False

if monotonic_upper:
    print("   ✅ 上曲線單調收斂")
if monotonic_lower:
    print("   ✅ 下曲線單調收斂")

output_file = "output/current/fairing_tail_fixed.vsp3"
print(f"\n生成: {output_file}")

VSPModelGenerator.create_fuselage(
    curves,
    name="Fairing_Tail_Fixed",
    filepath=output_file
)

print(f"\n✅ 完成！")
print(f"\n請在VSP GUI中檢查:")
print("  1. 尾部曲線應該平滑收斂，沒有扭曲")
print("  2. 上下表面應該完全平滑")
print("  3. 機頭部分是否改善")
print("="*80)
