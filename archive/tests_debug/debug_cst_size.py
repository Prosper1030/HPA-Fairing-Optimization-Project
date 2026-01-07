"""Debug CST 尺寸計算"""
import sys
sys.path.append('src')

from optimization.hpa_asymmetric_optimizer import CST_Modeler
import numpy as np

# 測試基因
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

print("="*60)
print("CST 尺寸計算診斷")
print("="*60)

# 生成曲線
curves = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=40)

# 找到最大值位置
max_width_idx = np.argmax(curves['width'])
max_width = curves['width'][max_width_idx]
max_width_psi = curves['psi'][max_width_idx]

print(f"\n寬度曲線:")
print(f"  期望最大寬度: {gene['W_max']:.4f} m")
print(f"  實際最大寬度: {max_width:.4f} m")
print(f"  位置 psi: {max_width_psi:.4f}")
print(f"  期望位置: {gene['X_max_pos']:.4f}")

# 檢查高度
max_top_idx = np.argmax(curves['top'])
max_top = curves['top'][max_top_idx]
max_top_psi = curves['psi'][max_top_idx]

max_bot_idx = np.argmax(np.abs(curves['bottom']))
max_bot = abs(curves['bottom'][max_bot_idx])
max_bot_psi = curves['psi'][max_bot_idx]

print(f"\n上部高度曲線:")
print(f"  期望最大高度: {gene['H_top_max']:.4f} m")
print(f"  實際最大高度: {max_top:.4f} m")
print(f"  位置 psi: {max_top_psi:.4f}")

print(f"\n下部高度曲線:")
print(f"  期望最大高度: {gene['H_bot_max']:.4f} m")
print(f"  實際最大高度: {max_bot:.4f} m")
print(f"  位置 psi: {max_bot_psi:.4f}")

# 檢查平均高度
height_avg = (curves['top'] + np.abs(curves['bottom'])) / 2.0
max_avg_idx = np.argmax(height_avg)
max_avg = height_avg[max_avg_idx]

print(f"\n平均高度:")
print(f"  期望: {(gene['H_top_max'] + gene['H_bot_max']) / 2:.4f} m")
print(f"  實際最大: {max_avg:.4f} m")

# 在 X_max_pos 處的實際值
target_psi = gene['X_max_pos']
idx = np.argmin(np.abs(curves['psi'] - target_psi))
actual_psi = curves['psi'][idx]

width_at_target = curves['width'][idx]
top_at_target = curves['top'][idx]
bot_at_target = abs(curves['bottom'][idx])
avg_at_target = (top_at_target + bot_at_target) / 2

print(f"\n在目標位置 psi={target_psi:.4f} (實際={actual_psi:.4f}) 處:")
print(f"  寬度: {width_at_target:.4f} m (期望 {gene['W_max']:.4f})")
print(f"  上高: {top_at_target:.4f} m (期望 {gene['H_top_max']:.4f})")
print(f"  下高: {bot_at_target:.4f} m (期望 {gene['H_bot_max']:.4f})")
print(f"  平均: {avg_at_target:.4f} m")

print(f"\n{'='*60}")
print("診斷結論:")
if abs(max_width - gene['W_max']) < 0.01:
    print("✅ 寬度計算正確")
else:
    print(f"❌ 寬度計算錯誤！差異: {max_width - gene['W_max']:.4f} m")
    print(f"   建議：可能需要除以 2 或乘以 2")

print(f"{'='*60}")
