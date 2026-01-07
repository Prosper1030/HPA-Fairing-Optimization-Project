"""
端到端測試驗證系統
測試數學驅動的 CST 幾何生成器與阻力分析
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 設置路徑
current_dir = os.path.dirname(__file__)
geometry_dir = os.path.join(current_dir, '..', 'src', 'geometry')
sys.path.insert(0, geometry_dir)

from cst_geometry_math_driven import CSTGeometryMathDriven

print("="*80)
print("🧪 數學驅動系統 - 端到端測試")
print("="*80)

# 基準設計
base_design = {
    "length": 2.5,
    "n_nose": 0.5,
    "n_tail": 1.0,
    "width_weights": [0.25, 0.35, 0.30, 0.10],
    "height_weights": [0.30, 0.45, 0.35, 0.10],
    "super_m": 2.5,
    "super_n": 2.5,
    "continuity": 1,
    "tangent_strength": 0.75,
    "run_drag_analysis": True
}

# 測試配置
test_cases = [
    {
        "name": "Test_Cosine40",
        "description": "全餘弦分佈 40 截面（推薦）",
        "num_sections": 40,
        "section_distribution": "cosine_full"
    },
    {
        "name": "Test_Uniform40",
        "description": "均勻分佈 40 截面（對比）",
        "num_sections": 40,
        "section_distribution": "uniform"
    },
    {
        "name": "Test_Cosine30",
        "description": "全餘弦分佈 30 截面（更快）",
        "num_sections": 30,
        "section_distribution": "cosine_full"
    },
]

# 創建生成器
generator = CSTGeometryMathDriven(output_dir="output")

# 執行測試
results_summary = []

print(f"\n開始測試 {len(test_cases)} 個配置...")
print(f"{'='*80}\n")

for i, test_case in enumerate(test_cases, 1):
    print(f"[測試 {i}/{len(test_cases)}] {test_case['description']}")

    # 合併配置
    design = {**base_design, **test_case}

    # 生成幾何並分析
    result = generator.generate_fuselage(design, verbose=True)

    # 保存結果摘要
    summary = {
        "name": test_case["name"],
        "description": test_case["description"],
        "sections": test_case["num_sections"],
        "distribution": test_case["section_distribution"],
        "time_geometry": result["timing"]["geometry"],
        "time_analysis": result["timing"]["analysis"],
        "time_total": result["timing"]["total"],
    }

    # 添加阻力結果（如果有）
    if "error" not in result["drag_results"]:
        summary.update({
            "drag_N": result["drag_results"].get("drag_force_N", None),
            "cd": result["drag_results"].get("drag_coefficient", None),
            "cda_m2": result["drag_results"].get("CdA_equivalent", None),
            "swet_m2": result["drag_results"].get("wetted_area_m2", None),
        })
    else:
        summary.update({
            "drag_N": None,
            "cd": None,
            "cda_m2": None,
            "swet_m2": None,
        })

    results_summary.append(summary)

# 輸出比較表格
print("\n" + "="*80)
print("📊 測試結果比較")
print("="*80)

# 表頭
header = (
    f"{'配置':<20} | "
    f"{'截面':<6} | "
    f"{'分佈':<12} | "
    f"{'阻力(N)':<10} | "
    f"{'CD':<10} | "
    f"{'時間(s)':<8}"
)
print(header)
print("-"*80)

# 數據行
for res in results_summary:
    drag_str = f"{res['drag_N']:.4f}" if res['drag_N'] else "N/A"
    cd_str = f"{res['cd']:.6f}" if res['cd'] else "N/A"

    row = (
        f"{res['name']:<20} | "
        f"{res['sections']:<6} | "
        f"{res['distribution']:<12} | "
        f"{drag_str:<10} | "
        f"{cd_str:<10} | "
        f"{res['time_total']:<8.2f}"
    )
    print(row)

print("="*80)

# 分析結果
print(f"\n💡 分析：")

if all(r['drag_N'] for r in results_summary):
    # 比較餘弦 vs 均勻
    cosine_40 = next((r for r in results_summary if r['name'] == 'Test_Cosine40'), None)
    uniform_40 = next((r for r in results_summary if r['name'] == 'Test_Uniform40'), None)

    if cosine_40 and uniform_40:
        drag_diff = abs(cosine_40['drag_N'] - uniform_40['drag_N'])
        drag_diff_pct = (drag_diff / cosine_40['drag_N']) * 100

        print(f"\n   餘弦 vs 均勻分佈（40截面）：")
        print(f"      阻力差異: {drag_diff:.4f} N ({drag_diff_pct:.2f}%)")

        if drag_diff_pct < 1.0:
            print(f"      ✅ 差異 < 1%，分佈對阻力影響小（幾何表示一致）")
        else:
            print(f"      ⚠️  差異 > 1%，可能存在幾何表示差異")

    # 比較截面數量影響
    cosine_30 = next((r for r in results_summary if r['name'] == 'Test_Cosine30'), None)

    if cosine_40 and cosine_30:
        time_saved = cosine_40['time_total'] - cosine_30['time_total']
        time_saved_pct = (time_saved / cosine_40['time_total']) * 100

        print(f"\n   40截面 vs 30截面（餘弦分佈）：")
        print(f"      時間節省: {time_saved:.2f}s ({time_saved_pct:.1f}%)")

        if cosine_30['drag_N']:
            drag_diff_30_40 = abs(cosine_40['drag_N'] - cosine_30['drag_N'])
            drag_diff_30_40_pct = (drag_diff_30_40 / cosine_40['drag_N']) * 100
            print(f"      阻力差異: {drag_diff_30_40:.4f} N ({drag_diff_30_40_pct:.2f}%)")

            if drag_diff_30_40_pct < 2.0:
                print(f"      ✅ 30截面已足夠準確（< 2% 差異）")
            else:
                print(f"      ⚠️  建議使用 40 截面以獲得更高精度")

# 合理性檢查
print(f"\n🔍 合理性檢查：")
print(f"   期望阻力範圍: 0.5-2.0 N (流線型機身 @ 6.5 m/s)")
print(f"   期望 CD 範圍: 0.0002-0.0005")

if cosine_40 and cosine_40['drag_N']:
    if 0.5 <= cosine_40['drag_N'] <= 2.0:
        print(f"   ✅ 阻力 {cosine_40['drag_N']:.4f} N 在合理範圍內")
    else:
        print(f"   ⚠️  阻力 {cosine_40['drag_N']:.4f} N 可能異常")

    if 0.0002 <= cosine_40['cd'] <= 0.0005:
        print(f"   ✅ CD {cosine_40['cd']:.6f} 在合理範圍內")
    else:
        print(f"   ⚠️  CD {cosine_40['cd']:.6f} 可能需要校驗")

print("\n" + "="*80)
print("✅ 端到端測試完成！")
print(f"📁 所有模型已保存在 output/ 目錄")
print("="*80)
