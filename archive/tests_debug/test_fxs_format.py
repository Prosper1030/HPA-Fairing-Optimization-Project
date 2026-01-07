"""測試 .fxs 格式是否正確"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp
import numpy as np

print("="*60)
print("測試 .fxs 格式")
print("="*60)

# 創建一個簡單的圓形 .fxs
output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

fxs_file = os.path.join(output_dir, "test_circle.fxs")

# 生成圓形點
n_points = 20
radius = 0.5

with open(fxs_file, 'w') as f:
    for i in range(n_points):
        theta = 2 * np.pi * i / n_points
        y = radius * np.cos(theta)
        z = radius * np.sin(theta)
        f.write(f"{y:.6f} {z:.6f}\n")

print(f"\n✅ 創建測試 .fxs 檔案: {fxs_file}")

# 讀取檔案檢查內容
with open(fxs_file, 'r') as f:
    lines = f.readlines()
    print(f"   檔案行數: {len(lines)}")
    print(f"   前 3 行:")
    for line in lines[:3]:
        print(f"      {line.strip()}")

# 嘗試在 VSP 中讀取
print("\n測試 VSP 讀取...")

vsp.ClearVSPModel()
fuse_id = vsp.AddGeom("FUSELAGE")

xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
vsp.ChangeXSecShape(xsec_surf, 1, vsp.XS_FILE_FUSE)

xsec = vsp.GetXSec(xsec_surf, 1)

abs_path = os.path.abspath(fxs_file)
print(f"   絕對路徑: {abs_path}")
print(f"   檔案存在: {os.path.exists(abs_path)}")

try:
    result = vsp.ReadFileXSec(xsec, abs_path)
    print(f"\n✅ ReadFileXSec 成功!")
    print(f"   返回值類型: {type(result)}")
    if hasattr(result, '__len__'):
        print(f"   返回值長度: {len(result)}")
except Exception as e:
    print(f"\n❌ ReadFileXSec 失敗: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
