"""修復現有檔案的ParasiteDrag設置"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp
from analysis.drag_analysis import DragAnalyzer

print("="*80)
print("修復 fairing_final_complete.vsp3 的ParasiteDrag設置")
print("="*80)

# 載入檔案
vsp.ClearVSPModel()
vsp.ReadVSPFile("output/current/fairing_final_complete.vsp3")
vsp.Update()

print("\n修復ParasiteDrag參數...")

pd_container = vsp.FindContainer("ParasiteDragSettings", 0)

if pd_container:
    # 使用與成功案例完全相同的設置
    params = [
        ("LengthUnit", 2.0, "meters"),
        ("Sref", 1.0, "1.0 m²"),
        ("Alt", 0.0, "0 m"),
        ("AltLengthUnit", 1.0, "meters"),
        ("Vinf", 6.5, "6.5 m/s"),
        ("VinfUnitType", 1.0, "m/s"),
        ("Temp", 15.0, "15°C"),
        ("TempUnit", 1.0, "Celsius"),
        ("DeltaTemp", 0.0, "0"),
        ("LamCfEqnType", 0.0, "Blasius"),
        ("TurbCfEqnType", 7.0, "Power Law Prandtl Low Re"),
        ("RefFlag", 0.0, "Manual"),
        ("Set", 0.0, "SET_ALL"),
    ]

    for parm_name, value, desc in params:
        parm = vsp.FindParm(pd_container, parm_name, "ParasiteDrag")
        if parm:
            vsp.SetParmVal(parm, value)
            print(f"  ✅ {parm_name} = {value} ({desc})")
        else:
            print(f"  ❌ 找不到: {parm_name}")

    vsp.Update()

# 保存為新檔案
output_file = "output/current/fairing_final_FIXED_DRAG.vsp3"
vsp.WriteVSPFile(output_file)
print(f"\n✅ 已保存: {output_file}")

# 立即用DragAnalyzer測試
print(f"\n{'='*80}")
print("測試阻力分析")
print(f"{'='*80}")

analyzer = DragAnalyzer(output_dir="output/results")

velocity = 6.5  # m/s
rho = 1.225  # kg/m³
mu = 1.7894e-5  # kg/(m·s)

result = analyzer.run_analysis(output_file, velocity, rho, mu)

if result:
    print(f"\n✅ 成功！")
    print(f"\n   Cd: {result.get('Cd', 'N/A')}")
    print(f"   CdA: {result.get('CdA', 'N/A')} m²")
    print(f"   Swet: {result.get('Swet', 'N/A')} m²")
    print(f"   Drag: {result.get('Drag', 'N/A')} N")

    # 與GUI對比
    gui_cd = 0.04121
    api_cd = result.get('Cd', 0)

    print(f"\n   與GUI對比：")
    print(f"   GUI CD: {gui_cd}")
    print(f"   API CD: {api_cd}")
    if api_cd > 0:
        diff_pct = abs(api_cd - gui_cd) / gui_cd * 100
        print(f"   差異: {diff_pct:.2f}%")
else:
    print(f"\n❌ 仍然失敗")

print(f"\n{'='*80}")
