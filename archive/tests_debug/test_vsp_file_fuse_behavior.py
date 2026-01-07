"""測試 VSP FILE_FUSE 是否會標準化非對稱形狀"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp
from optimization.hpa_asymmetric_optimizer import CST_Modeler

print("="*60)
print("測試 VSP FILE_FUSE 行為")
print("="*60)

# 1. 生成明顯上下非對稱的 .fxs
y_half = 0.3
z_top = 0.95
z_bot = 0.35

fxs_file = "output/test_asymmetric.fxs"

print(f"\n📝 生成測試 .fxs:")
print(f"   半寬: {y_half} m")
print(f"   上高: {z_top} m")
print(f"   下高: {z_bot} m")

CST_Modeler.write_fxs_file(fxs_file, y_half, z_top, z_bot, n_points=60, exponent=2.5)

# 驗證 .fxs 內容
with open(fxs_file, 'r') as f:
    lines = f.readlines()
    zs = [float(line.split()[1]) for line in lines if line.strip()]
    print(f"   .fxs 中 Z 範圍: [{min(zs):.3f}, {max(zs):.3f}]")

# 2. 在 VSP 中創建 FILE_FUSE 截面
vsp.ClearVSPModel()
fuse_id = vsp.AddGeom("FUSELAGE")

xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

# 改變第 1 個截面為 FILE_FUSE
vsp.ChangeXSecShape(xsec_surf, 1, vsp.XS_FILE_FUSE)
xsec = vsp.GetXSec(xsec_surf, 1)

# 讀取 .fxs
abs_path = os.path.abspath(fxs_file)
print(f"\n📖 讀取 .fxs 到 VSP...")
vsp.ReadFileXSec(xsec, abs_path)

# 設置 Width 和 Height
total_width = y_half * 2
total_height = z_top + z_bot

print(f"\n⚙️ 設置參數:")
print(f"   Width: {total_width:.3f} m")
print(f"   Height: {total_height:.3f} m")

width_parm = vsp.GetXSecParm(xsec, "Width")
if width_parm:
    vsp.SetParmVal(width_parm, total_width)

height_parm = vsp.GetXSecParm(xsec, "Height")
if height_parm:
    vsp.SetParmVal(height_parm, total_height)

vsp.Update()

# 3. 保存並重新讀取，檢查形狀是否保持非對稱
test_vsp = "output/test_file_fuse.vsp3"
vsp.WriteVSPFile(test_vsp)

print(f"\n💾 保存模型: {test_vsp}")
print(f"\n📋 請在 VSP GUI 中打開此檔案，檢查截面 1:")
print(f"   1. 在 XSec 面板中選擇截面 1")
print(f"   2. 查看截面形狀是否上下非對稱")
print(f"   3. 期望：上半部明顯比下半部大")
print(f"   4. 如果看到對稱的橢圓，說明 VSP 強制標準化了形狀")

# 4. 嘗試讀取原始點（如果 API 支持）
print(f"\n🔍 嘗試從 VSP 讀回點...")
try:
    # VSP 可能沒有直接獲取點的 API
    # 但我們可以檢查參數
    print(f"   Width: {vsp.GetParmVal(width_parm):.3f} m")
    print(f"   Height: {vsp.GetParmVal(height_parm):.3f} m")

    # 檢查是否有其他參數控制非對稱
    area_parm = vsp.GetXSecParm(xsec, "Area")
    if area_parm:
        print(f"   Area: {vsp.GetParmVal(area_parm):.3f} m²")

except Exception as e:
    print(f"   無法獲取參數: {e}")

print("\n" + "="*60)
print("請打開 output/test_file_fuse.vsp3 並檢查截面形狀！")
print("="*60)
