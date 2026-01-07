"""
嘗試通過不同的方式找到 ParasiteDrag 參數
"""
import openvsp as vsp

print("="*80)
print("🔍 探索參數訪問方式")
print("="*80)

# 載入檔案
test_file = "output/Fixed_Angles_Test.vsp3"
vsp.ClearVSPModel()
vsp.ReadVSPFile(test_file)
vsp.Update()

geom_ids = vsp.FindGeoms()
geom_id = geom_ids[0]
geom_name = vsp.GetGeomName(geom_id)

print(f"\n📁 模型: {test_file}")
print(f"📦 幾何: {geom_name} (ID: {geom_id})")

# 獲取所有參數
print(f"\n🔍 獲取所有參數...")
parm_ids = vsp.GetGeomParmIDs(geom_id)
print(f"   總數: {len(parm_ids)}")

# 搜索 ParasiteDragProps 相關參數
print(f"\n🔍 搜索 ParasiteDragProps 中列出的參數:")
target_names = ["FFBodyEqnType", "FFUser", "FFWingEqnType", "PercLam", "Q", "Roughness"]

for parm_id in parm_ids:
    parm_name = vsp.GetParmName(parm_id)
    parm_container = vsp.GetParmContainer(parm_id)

    if parm_name in target_names:
        val = vsp.GetParmVal(parm_id)
        print(f"   ✅ 找到: {parm_container}::{parm_name} = {val} (ID: {parm_id})")

# 嘗試使用 GetParm 和 FindParm
print(f"\n🔍 嘗試 FindParm:")
for name in target_names:
    # 嘗試不同的 Container 名稱
    containers = ["ParasiteDragProps", "ParasiteDrag", "Design", "XForm"]
    for container in containers:
        parm_id = vsp.FindParm(geom_id, name, container)
        if parm_id:
            val = vsp.GetParmVal(parm_id)
            print(f"   ✅ FindParm({name}, {container}): {val}")
            break
    else:
        print(f"   ❌ FindParm({name}, *): 未找到")

# 嘗試直接用 GetParmVal (geom_id, name, group)
print(f"\n🔍 嘗試 GetParmVal(geom_id, name, group):")
for name in target_names:
    containers = ["ParasiteDragProps", "ParasiteDrag", "Design"]
    for container in containers:
        try:
            val = vsp.GetParmVal(geom_id, name, container)
            print(f"   ✅ GetParmVal({name}, {container}): {val}")
            break
        except:
            pass
    else:
        print(f"   ❌ GetParmVal({name}, *): 未找到")

print("\n" + "="*80)
