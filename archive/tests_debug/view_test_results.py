"""查看固定參數測試結果"""
import os

print("="*80)
print("HPA 測試結果查看")
print("="*80)

csv_file = "output/test_hpa_fixed_params_ParasiteBuildUp.csv"

if os.path.exists(csv_file):
    with open(csv_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    print("\n✅ 阻力分析結果:")
    for line in lines:
        if 'HPA_Test_Fixed' in line:
            parts = [p.strip() for p in line.split(',')]
            swet = float(parts[1])
            cd = float(parts[-2])

            q = 0.5 * 1.225 * (6.5 ** 2)
            drag = q * swet * cd

            print(f"   Swet = {swet:.3f} m²")
            print(f"   Cd   = {cd:.6f}")
            print(f"   Drag = {drag:.4f} N")
            break

    print(f"\n💡 檢查清單:")
    print(f"   1. 用 OpenVSP GUI 打開: output/test_hpa_fixed_params.vsp3")
    print(f"   2. 檢查截面分布（機頭機尾是否密集?）")
    print(f"   3. 檢查表面光滑度（有無扭曲?）")
    print(f"   4. 確認形狀合理後，可以開始 GA 優化")
else:
    print(f"\n❌ 找不到結果檔案: {csv_file}")
    print(f"   請先運行: python tests/test_hpa_fixed_params.py")

print(f"\n{'='*80}")
