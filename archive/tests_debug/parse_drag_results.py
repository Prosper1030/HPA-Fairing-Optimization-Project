"""解析阻力結果並計算"""
import csv

csv_file = "Unnamed_ParasiteBuildUp.csv"

print("="*80)
print("解析 ParasiteDrag 結果")
print("="*80)

with open(csv_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 解析主要數據
swet = None
cda = None
cd_given = None

for line in lines:
    if line.strip().startswith("TestFuselage"):
        parts = [p.strip() for p in line.split(',')]
        swet = float(parts[1])      # S_wet (m²)
        cda = float(parts[10])      # f (CdA)  (m²)
        cd_given = float(parts[11]) # Cd
        break

print(f"\n從 CSV 讀取：")
print(f"  濕潤表面積 S_wet = {swet:.6f} m²")
print(f"  阻力面積 CdA = {cda:.6f} m²")
print(f"  給定的 Cd = {cd_given:.6f}")

# 計算理論投影面積
W_max = 0.601  # m (實際寬度)
H_total = 1.303  # m (總高度)
import math
proj_area = math.pi * (W_max / 2) * (H_total / 2)

print(f"\n理論投影面積（橢圓近似）：")
print(f"  寬度 = {W_max:.3f} m")
print(f"  高度 = {H_total:.3f} m")
print(f"  投影面積 = {proj_area:.6f} m²")

# 計算基於投影面積的 Cd
cd_proj = cda / proj_area
drag_counts = cd_proj * 10000

print(f"\n基於投影面積的阻力係數：")
print(f"  Cd = {cd_proj:.6f} (Sref = 投影面積)")
print(f"  阻力計數 = {drag_counts:.1f} counts")

# 計算阻力力量（15 m/s）
rho = 1.204  # kg/m³ (20°C, 1 atm)
v = 15.0     # m/s
q = 0.5 * rho * v**2  # 動壓

drag_force = q * cda
print(f"\n阻力力量 @ {v} m/s：")
print(f"  動壓 q = {q:.2f} Pa")
print(f"  阻力 D = q × CdA = {drag_force:.4f} N")

# 也可以用 Cd 計算
drag_force_alt = q * cd_proj * proj_area
print(f"  驗證: D = q × Cd × S = {drag_force_alt:.4f} N")

print(f"\n摘要：")
print(f"  ┌{'─'*60}┐")
print(f"  │ 投影面積：{proj_area:.6f} m²{' '*(37-len(f'{proj_area:.6f}'))}│")
print(f"  │ 濕潤表面積：{swet:.6f} m²{' '*(35-len(f'{swet:.6f}'))}│")
print(f"  │ 阻力面積 CdA：{cda:.6f} m²{' '*(34-len(f'{cda:.6f}'))}│")
print(f"  │ 阻力係數 Cd：{cd_proj:.6f} (基於投影面積){' '*(18-len(f'{cd_proj:.6f}'))}│")
print(f"  │ 阻力計數：{drag_counts:.1f} counts{' '*(39-len(f'{drag_counts:.1f}'))}│")
print(f"  │ 阻力力量：{drag_force:.4f} N @ 15 m/s{' '*(27-len(f'{drag_force:.4f}'))}│")
print(f"  └{'─'*60}┘")

print("\n" + "="*80)
print("✅ 解析完成！")
print("="*80)
