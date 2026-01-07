"""整理output資料夾結構"""
import os
import shutil
from pathlib import Path

output_dir = Path("output")

# 建立子資料夾
folders = {
    'archive': output_dir / 'archive',           # 舊測試檔案
    'results': output_dir / 'results',           # CompGeom/ParasiteDrag結果
    'plots': output_dir / 'plots',               # 圖片
    'temp': output_dir / 'temp',                 # 臨時檔案（.fxs等）
    'current': output_dir / 'current',           # 當前工作檔案
}

for folder in folders.values():
    folder.mkdir(exist_ok=True)

print("="*80)
print("整理output資料夾")
print("="*80)

# 定義分類規則
rules = {
    'current': [
        'fairing_skinning_fixed.vsp3',
        'fairing_zloc_fixed_v2.vsp3',
        'Example.vsp3',
    ],
    'plots': [
        '*.png',
    ],
    'results': [
        '*_CompGeom.csv',
        '*_CompGeom.txt',
        '*_ParasiteBuildUp.csv',
        'parasitedrag_gui.csv',
    ],
    'temp': [
        '*.fxs',
    ],
    'archive': [
        # 所有測試檔案
        'Test_*.vsp3',
        'test_*.vsp3',
        'Quick*.vsp3',
        '*_sections.vsp3',
        '*_sections_opt.vsp3',
        'Type_*.vsp3',
        '*_Distribution.vsp3',
        '*_Dense.vsp3',
        'MathDriven*.vsp3',
        'Fixed_*.vsp3',
        'Final_*.vsp3',
    ],
}

# 統計
stats = {key: 0 for key in rules.keys()}

# 移動檔案
from fnmatch import fnmatch

for category, patterns in rules.items():
    print(f"\n📁 {category}:")
    for pattern in patterns:
        for file in output_dir.glob(pattern):
            # 只處理檔案，跳過資料夾
            if not file.is_file():
                continue

            # 跳過已經在子資料夾中的檔案
            if file.parent != output_dir:
                continue

            dest = folders[category] / file.name

            try:
                shutil.move(str(file), str(dest))
                print(f"   ✅ {file.name}")
                stats[category] += 1
            except Exception as e:
                print(f"   ❌ {file.name}: {e}")

print("\n" + "="*80)
print("📊 統計:")
print("="*80)
for category, count in stats.items():
    print(f"   {category}: {count} 個檔案")

print("\n" + "="*80)
print("✅ 整理完成！")
print("="*80)
print("\n資料夾結構:")
print("  output/")
print("    ├── current/      # 當前工作檔案（最新修復版本）")
print("    ├── archive/      # 舊測試檔案")
print("    ├── results/      # 分析結果（CSV/TXT）")
print("    ├── plots/        # 圖片")
print("    ├── temp/         # 臨時檔案（.fxs）")
print("    ├── runs/         # GA運行資料夾（保持原樣）")
print("    └── hpa_run_*/    # GA運行資料夾（保持原樣）")
print("="*80)
