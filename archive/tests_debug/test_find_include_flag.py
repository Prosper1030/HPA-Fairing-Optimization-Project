"""
搜索控制幾何是否包含在 ParasiteDrag 計算中的參數
"""
import openvsp as vsp

print("="*80)
print("🔍 搜索 Include/Enable 參數")
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
print(f"📦 幾何: {geom_name}")

# 獲取所有參數
parm_ids = vsp.GetGeomParmIDs(geom_id)

# 搜索包含 "include", "enable", "parasit", "drag" 的參數
keywords = ["include", "enable", "parasit", "drag", "expanded", "incorporated"]

print(f"\n🔍 搜索包含關鍵字的參數:")
found = {}
for parm_id in parm_ids:
    parm_name = vsp.GetParmName(parm_id).lower()
    parm_container = vsp.GetParmContainer(parm_id)

    for keyword in keywords:
        if keyword in parm_name or keyword in parm_container.lower():
            val = vsp.GetParmVal(parm_id)
            full_name = f"{parm_container}::{vsp.GetParmName(parm_id)}"
            if full_name not in found:
                found[full_name] = val

for full_name, val in sorted(found.items()):
    print(f"   {full_name} = {val}")

# 檢查 ParasiteDragProps 容器中的所有參數
print(f"\n🔍 ParasiteDragProps 容器中的所有參數:")
for parm_id in parm_ids:
    parm_container = vsp.GetParmContainer(parm_id)
    if "parasitedrag" in parm_container.lower():
        parm_name = vsp.GetParmName(parm_id)
        val = vsp.GetParmVal(parm_id)
        print(f"   {parm_container}::{parm_name} = {val}")

print("\n" + "="*80)
