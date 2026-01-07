"""分析切線角度的邏輯是否正確"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from optimization.hpa_asymmetric_optimizer import CST_Modeler, CSTDerivatives
import numpy as np

print("="*80)
print("切線角度邏輯分析")
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

curves = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=40)
weights_fixed = np.array([1.0, 1.0])

print("\n🔍 關鍵問題：")
print("   VSP的SetXSecTanAngles()中的'top'和'bottom'角度代表什麼？")
print("")
print("   假設A: 控制截面「高度曲線」的切線（上下應該相同）")
print("   假設B: 分別控制z_upper和z_lower邊界曲線的切線（上下可以不同）")
print("")

print("\n📊 測試幾個關鍵截面:")
print("-" * 80)

test_sections = [0, 10, 20, 30, 39]

for i in test_sections:
    psi = curves['psi'][i]
    z_upper = curves['z_upper'][i]
    z_lower = curves['z_lower'][i]
    z_loc = curves['z_loc'][i]
    super_height = curves['super_height'][i]

    print(f"\n截面 {i} (psi={psi:.3f}):")
    print(f"   z_upper = {z_upper:.3f} m")
    print(f"   z_lower = {z_lower:.3f} m")
    print(f"   z_loc = {z_loc:.3f} m")
    print(f"   super_height = {super_height:.3f} m")

    # 當前方法：用不同的N2計算
    tangent_top = CSTDerivatives.compute_tangent_angles_for_section(
        psi, gene['N1'], gene['N2_top'], weights_fixed, weights_fixed, gene['L']
    )
    tangent_bot = CSTDerivatives.compute_tangent_angles_for_section(
        psi, gene['N1'], gene['N2_bot'], weights_fixed, weights_fixed, gene['L']
    )

    print(f"   當前方法（用N2_top={gene['N2_top']}, N2_bot={gene['N2_bot']}）:")
    print(f"      angle_top = {tangent_top['top']:.1f}°")
    print(f"      angle_bot = {tangent_bot['bottom']:.1f}°")
    print(f"      差異 = {abs(tangent_top['top'] - tangent_bot['bottom']):.1f}°")

    # 檢查對稱性
    if abs(z_upper - z_lower) < 0.01:  # 幾何對稱
        print(f"   ⚠️ 幾何對稱但角度不同！（差 {abs(tangent_top['top'] - tangent_bot['bottom']):.1f}°）")

print("\n" + "="*80)
print("🤔 分析:")
print("="*80)

print("\n1. 機頭（截面0）:")
print("   - z_upper = z_lower = 0 （完全對稱）")
print("   - angle_top = angle_bot = 90° （角度相同）✅")
print("   - 結論：機頭沒問題")

print("\n2. 機尾（截面39）:")
print("   - z_upper = z_lower = 0.1 （完全對稱）")
print("   - 但 angle_top ≠ angle_bot （相差7.2°）❌")
print("   - 問題：幾何對稱但角度不同！")

print("\n3. 中間截面（10, 20, 30）:")
print("   - z_upper ≠ z_lower （非對稱）")
print("   - angle_top ≠ angle_bot （角度不同）")
print("   - 問題：這樣對嗎？")

print("\n" + "="*80)
print("💡 可能的解決方案:")
print("="*80)

print("\n方案1: 使用統一的N2")
print("   - 上下都用 N2_avg = (N2_top + N2_bot) / 2")
print("   - 優點：機頭機尾對稱處角度會相同")
print("   - 缺點：無法反映上下邊界的不同形狀")

print("\n方案2: 分別計算z_upper和z_lower曲線的切線")
print("   - 需要新的計算方法，直接從z_upper(x)和z_lower(x)計算dz/dx")
print("   - 優點：真正反映上下邊界的形狀")
print("   - 缺點：需要重新實現，而且可能與VSP的角度定義不符")

print("\n方案3: 特殊處理機頭和機尾")
print("   - 機頭/機尾（對稱處）：強制使用相同角度")
print("   - 中間截面：使用當前方法（不同N2）")
print("   - 優點：解決機頭機尾的問題")
print("   - 缺點：需要判斷哪些是對稱截面")

print("\n" + "="*80)
print("🔬 需要實驗驗證:")
print("="*80)
print("1. 在VSP中手動調整一個截面的top/bottom角度，觀察效果")
print("2. 確認VSP的角度定義到底是控制什麼")
print("3. 根據實驗結果選擇正確的方案")
print("="*80)
