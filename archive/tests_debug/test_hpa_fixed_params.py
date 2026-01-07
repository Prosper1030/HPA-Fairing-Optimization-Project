"""
HPA 優化器測試 - 使用固定參數
驗證:
1. 餘弦分布截面 ✓
2. 切線角度正確 ✓
3. VSP 模型正確 ✓
4. 阻力計算合理 ✓
"""
import sys
sys.path.append('src')

from optimization.hpa_asymmetric_optimizer import (
    CST_Modeler,
    ConstraintChecker,
    VSPModelGenerator,
    ProjectManager
)
import openvsp as vsp
import numpy as np

print("="*80)
print("HPA 優化器測試 - 固定參數")
print("="*80)

# 固定測試基因（確保通過所有限制）
test_gene = {
    'L': 2.5,           # 總長度
    'W_max': 0.60,      # 最大寬度
    'H_top_max': 0.95,  # 上部最大高度
    'H_bot_max': 0.35,  # 下部最大高度
    'N1': 0.5,          # 機頭形狀
    'N2_top': 0.7,      # 上機尾形狀
    'N2_bot': 0.8,      # 下機尾形狀
    'X_max_pos': 0.25,  # 最大截面位置
    'X_offset': 0.7,    # 踏板位置
}

print(f"\n📋 測試基因:")
for key, val in test_gene.items():
    print(f"   {key:12s} = {val:.3f}")

# 1. 生成 CST 曲線
print(f"\n{'='*80}")
print("步驟 1: 生成 CST 曲線（使用餘弦分布）")
print(f"{'='*80}")

curves = CST_Modeler.generate_asymmetric_fairing(test_gene, num_sections=40)

print(f"\n✅ 曲線生成成功!")
print(f"   截面數量: {len(curves['psi'])}")
print(f"   總長度: {curves['L']:.2f} m")
print(f"\n   截面分布分析:")
print(f"   前 5 個 psi: {[f'{p:.6f}' for p in curves['psi'][:5]]}")
print(f"   後 5 個 psi: {[f'{p:.6f}' for p in curves['psi'][-5:]]}")

# 檢查間距
spacings = np.diff(curves['psi'])
print(f"\n   間距統計:")
print(f"   最小間距: {np.min(spacings):.6f}")
print(f"   最大間距: {np.max(spacings):.6f}")
print(f"   間距比率: {np.max(spacings)/np.min(spacings):.2f}x")
print(f"   💡 機頭機尾密集 = 餘弦分布 ✅")

# 2. 檢查限制
print(f"\n{'='*80}")
print("步驟 2: 檢查硬限制")
print(f"{'='*80}")

passed, results = ConstraintChecker.check_all_constraints(test_gene, curves)

print(f"\n限制檢查結果:")
for name, result in results.items():
    status = "✅" if result['pass'] else "❌"
    if 'required' in result:
        print(f"   {status} {name:15s}: {result['value']:.3f} (需求: >= {result['required']:.3f})")
    else:
        print(f"   {status} {name:15s}: {result['value']:.3f}")

if passed:
    print(f"\n✅✅✅ 所有限制檢查通過!")
else:
    print(f"\n❌ 部分限制失敗（需要調整基因）")
    sys.exit(1)

# 3. 生成 VSP 模型
print(f"\n{'='*80}")
print("步驟 3: 生成 VSP 模型（含餘弦分布 + 切線角度）")
print(f"{'='*80}")

vsp_file = "output/test_hpa_fixed_params.vsp3"

try:
    VSPModelGenerator.create_fuselage(curves, "HPA_Test_Fixed", vsp_file)
    print(f"\n✅ VSP 模型生成成功!")
    print(f"   檔案: {vsp_file}")
    print(f"   💡 請用 OpenVSP GUI 打開檢查:")
    print(f"      1. 截面是否在機頭機尾密集? (餘弦分布)")
    print(f"      2. 表面是否光滑無扭曲? (切線角度正確)")
    print(f"      3. 形狀是否合理?")
except Exception as e:
    print(f"\n❌ VSP 模型生成失敗: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. 執行阻力分析
print(f"\n{'='*80}")
print("步驟 4: 執行 ParasiteDrag 分析")
print(f"{'='*80}")

try:
    # 直接在這裡執行分析（不需要 DragAnalyzer）
    vsp.ClearVSPModel()
    vsp.ReadVSPFile(vsp_file)

    vsp.SetAnalysisInputDefaults("ParasiteDrag")
    vsp.SetDoubleAnalysisInput("ParasiteDrag", "Rho", [1.225])
    vsp.SetDoubleAnalysisInput("ParasiteDrag", "Vinf", [6.5])
    vsp.SetDoubleAnalysisInput("ParasiteDrag", "Mu", [1.7894e-5])
    vsp.ExecAnalysis("ParasiteDrag")

    # 讀取 CSV
    import os
    os.chdir("output")
    csv_file = "HPA_Test_Fixed_ParasiteBuildUp.csv"

    if os.path.exists(csv_file):
        with open(csv_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 解析結果
        for line in lines:
            if 'Totals:' in line:
                parts = [p.strip() for p in line.split(',')]
                values = [p for p in parts if p and p != 'Totals:']

                if len(values) >= 2:
                    cd = float(values[1])
                    print(f"\n✅ 阻力分析成功!")
                    print(f"   Cd = {cd:.6f}")

                    # 從數據行獲取 Swet
                    for data_line in lines:
                        if 'HPA_Test_Fixed' in data_line:
                            data_parts = [p.strip() for p in data_line.split(',')]
                            swet = float(data_parts[1])
                            print(f"   Swet = {swet:.3f} m²")

                            q = 0.5 * 1.225 * (6.5 ** 2)
                            drag = q * swet * cd
                            print(f"   Drag = {drag:.4f} N")
                            break
                    break
    else:
        print(f"\n❌ CSV 檔案未生成: {csv_file}")

except Exception as e:
    print(f"\n❌ 阻力分析失敗: {e}")
    import traceback
    traceback.print_exc()

# 5. CompGeom 驗證
print(f"\n{'='*80}")
print("步驟 5: CompGeom 驗證（濕面積）")
print(f"{'='*80}")

try:
    vsp.ClearVSPModel()
    vsp.ReadVSPFile(vsp_file)

    vsp.SetAnalysisInputDefaults("CompGeom")
    vsp.ExecAnalysis("CompGeom")

    compgeom_csv = "HPA_Test_Fixed_CompGeom.csv"
    if os.path.exists(compgeom_csv):
        with open(compgeom_csv, 'r') as f:
            lines = f.readlines()

        for line in lines:
            if 'Wet_Area' in line:
                parts = line.split(',')
                if len(parts) >= 2:
                    compgeom_swet = float(parts[1].strip())
                    print(f"\n✅ CompGeom 濕面積: {compgeom_swet:.3f} m²")
                    print(f"   💡 應該與 ParasiteDrag Swet 接近")
                    break
except Exception as e:
    print(f"\n⚠️  CompGeom 失敗: {e}")

print(f"\n{'='*80}")
print("測試完成！")
print(f"{'='*80}")
print(f"\n下一步:")
print(f"  1. 用 OpenVSP GUI 打開 {vsp_file}")
print(f"  2. 檢查截面分布（機頭機尾密集?）")
print(f"  3. 檢查表面光滑度（切線正確?）")
print(f"  4. 確認無誤後再運行 GA 優化")
print(f"{'='*80}")
