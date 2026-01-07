"""
調試幾何集設置
檢查模型中的幾何以及它們所屬的集合
"""
import openvsp as vsp
import sys

print("="*80)
print("🔍 調試幾何集設置")
print("="*80)

# 載入模型
test_file = "output/Fixed_Angles_Test.vsp3"
vsp.ClearVSPModel()
vsp.ReadVSPFile(test_file)
vsp.Update()

print(f"\n📁 模型: {test_file}")

# 獲取所有幾何
geom_ids = vsp.FindGeoms()
print(f"\n📦 幾何數量: {len(geom_ids)}")

for i, geom_id in enumerate(geom_ids):
    name = vsp.GetGeomName(geom_id)
    geom_type = vsp.GetGeomTypeName(geom_id)

    print(f"\n幾何 {i+1}:")
    print(f"   ID: {geom_id}")
    print(f"   名稱: {name}")
    print(f"   類型: {geom_type}")

    # 檢查各個集合的狀態
    print(f"   所屬集合:")
    for set_idx in range(20):  # 檢查前 20 個集合
        try:
            is_in_set = vsp.GetSetFlag(geom_id, set_idx)
            if is_in_set:
                set_name = vsp.GetSetName(set_idx)
                print(f"      Set {set_idx} ({set_name}): YES")
        except:
            break

# 列出所有可用的集合
print(f"\n📋 可用的集合:")
for set_idx in range(20):
    try:
        set_name = vsp.GetSetName(set_idx)
        if set_name:
            print(f"   Set {set_idx}: {set_name}")
    except:
        break

# 檢查 VSP 預定義常量
print(f"\n🔧 VSP 預定義集合常量:")
print(f"   SET_ALL = {vsp.SET_ALL}")
print(f"   SET_SHOWN = {vsp.SET_SHOWN}")
print(f"   SET_NOT_SHOWN = {vsp.SET_NOT_SHOWN}")
print(f"   SET_FIRST_USER = {vsp.SET_FIRST_USER}")

print("\n" + "="*80)
