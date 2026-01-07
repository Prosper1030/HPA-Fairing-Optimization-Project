"""
對比測試：用同樣的腳本測試兩個文件
1. Type_A_Standard.vsp3（已知能成功）
2. Fixed_Angles_Test.vsp3（我的文件，失敗）
"""
import sys
sys.path.append('src')

from analysis.drag_analysis import DragAnalyzer

print("="*80)
print("🧪 對比測試：成功的文件 vs 我的文件")
print("="*80)

# 測試參數（相同）
velocity = 6.5  # m/s
rho = 1.225  # kg/m³
mu = 1.7894e-5  # kg/(m·s)

analyzer = DragAnalyzer(output_dir="output")

# ========== 測試 1：Type_A_Standard（已知能成功）==========
print(f"\n{'='*80}")
print(f"測試 1：Type_A_Standard.vsp3（已知能成功）")
print(f"{'='*80}")

try:
    result1 = analyzer.run_analysis(
        "output/Type_A_Standard.vsp3",
        velocity,
        rho,
        mu
    )

    if result1:
        print(f"\n✅ 成功！")
        print(f"   CdA: {result1.get('CdA', 'N/A')}")
        print(f"   Cd: {result1.get('Cd', 'N/A')}")
        print(f"   Swet: {result1.get('Swet', 'N/A')}")
        print(f"   Drag: {result1.get('Drag', 'N/A')}")
    else:
        print(f"\n❌ 失敗：無法解析結果")

except Exception as e:
    print(f"\n❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()

# ========== 測試 2：Fixed_Angles_Test（我的文件）==========
print(f"\n{'='*80}")
print(f"測試 2：Fixed_Angles_Test.vsp3（我的文件）")
print(f"{'='*80}")

try:
    result2 = analyzer.run_analysis(
        "output/Fixed_Angles_Test.vsp3",
        velocity,
        rho,
        mu
    )

    if result2:
        print(f"\n✅ 成功！")
        print(f"   CdA: {result2.get('CdA', 'N/A')}")
        print(f"   Cd: {result2.get('Cd', 'N/A')}")
        print(f"   Swet: {result2.get('Swet', 'N/A')}")
        print(f"   Drag: {result2.get('Drag', 'N/A')}")

        # 與 GUI 對比
        gui_cd = 0.02045
        api_cd = result2.get('Cd', 0)
        if api_cd:
            diff_pct = abs(api_cd - gui_cd) / gui_cd * 100
            print(f"\n💡 與 GUI 對比:")
            print(f"   GUI CD: {gui_cd}")
            print(f"   API CD: {api_cd}")
            print(f"   差異: {diff_pct:.2f}%")

            if diff_pct < 5.0:
                print(f"\n   ✅✅✅ 成功！差異 < 5%")

    else:
        print(f"\n❌ 失敗：無法生成或解析 CSV")
        print(f"   提示：這個文件可能有問題")

except Exception as e:
    print(f"\n❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()

print(f"\n{'='*80}")
