"""
測試：完全模仿成功的 drag_analysis.py 腳本
只設置 Rho, Vinf, Mu，其他參數使用文件中保存的設置
"""
import openvsp as vsp
import os

print("="*80)
print("🧪 測試：模仿成功腳本的簡單方法")
print("="*80)

# 測試參數
test_file = "output/Fixed_Angles_Test.vsp3"
velocity = 6.5  # m/s
rho = 1.225  # kg/m³
mu = 1.7894e-5  # kg/(m·s)

name = os.path.basename(test_file).replace(".vsp3", "")

print(f"\n📁 模型: {name}")
print(f"   Velocity: {velocity} m/s")
print(f"   Rho: {rho} kg/m³")
print(f"   Mu: {mu} kg/(m·s)")

# 載入模型
print(f"\n📥 載入模型...")
vsp.ClearVSPModel()
vsp.ReadVSPFile(test_file)

# 設置分析（完全模仿 drag_analysis.py）
print(f"\n⚙️  設置分析...")
analysis_name = "ParasiteDrag"
vsp.SetAnalysisInputDefaults(analysis_name)
vsp.SetDoubleAnalysisInput(analysis_name, "Rho", [rho])
vsp.SetDoubleAnalysisInput(analysis_name, "Vinf", [velocity])
vsp.SetDoubleAnalysisInput(analysis_name, "Mu", [mu])

print(f"   ✅ 僅設置 Rho, Vinf, Mu")
print(f"   ✅ 其他參數使用文件中保存的設置")

# 執行分析
print(f"\n🚀 執行分析...")
result_id = vsp.ExecAnalysis(analysis_name)

# 檢查是否生成了 CSV
generated_csv = f"{name}_ParasiteBuildUp.csv"
print(f"\n📊 檢查結果...")

if os.path.exists(generated_csv):
    print(f"   ✅ CSV 已生成: {generated_csv}")

    # 讀取並顯示結果
    with open(generated_csv, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        print(f"\n📄 CSV 內容:")
        for line in lines[:20]:  # 顯示前 20 行
            print(f"   {line.rstrip()}")

    # 解析關鍵數據
    for line in lines:
        if "Total" in line and "," in line:
            parts = line.split(',')
            if len(parts) > 10:
                try:
                    cd = float(parts[-2].strip())
                    print(f"\n💡 總 CD: {cd:.6f}")
                    print(f"   GUI CD: 0.02045")
                    diff_pct = abs(cd - 0.02045) / 0.02045 * 100
                    print(f"   差異: {diff_pct:.2f}%")

                    if diff_pct < 5.0:
                        print(f"\n   ✅✅✅ 成功！這個簡單方法有效！")
                    break
                except:
                    pass
else:
    print(f"   ❌ 未生成 CSV 文件")
    print(f"   可能分析失敗，檢查 VSP 文件中保存的設置")

print("\n" + "="*80)
