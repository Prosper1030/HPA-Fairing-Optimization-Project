"""
探索幾何體上有哪些 ParasiteDrag 相關的參數
"""
import openvsp as vsp

print("="*80)
print("🔍 探索 ParasiteDrag 參數")
print("="*80)

# 載入模型
test_file = "output/Fixed_Angles_Test.vsp3"
vsp.ClearVSPModel()
vsp.ReadVSPFile(test_file)
vsp.Update()

geom_ids = vsp.FindGeoms()
print(f"\n📁 模型: {test_file}")
print(f"📦 幾何數量: {len(geom_ids)}")

for geom_id in geom_ids:
    geom_name = vsp.GetGeomName(geom_id)
    print(f"\n幾何: {geom_name} (ID: {geom_id})")

    # 列出所有 Container (群組)
    print(f"\n  可用的 Container (群組):")
    # 嘗試常見的群組名稱
    common_groups = ["Design", "XForm", "ParasiteDrag", "Parasite_Drag", "Mass_Props"]
    for group in common_groups:
        try:
            # 嘗試獲取這個群組中的第一個參數來測試群組是否存在
            parm_ids = vsp.GetGeomParmIDs(geom_id)
            for parm_id in parm_ids:
                parm_container = vsp.GetParmContainer(parm_id)
                if group.lower() in parm_container.lower():
                    print(f"    ✅ {group} 存在")
                    break
        except:
            pass

print(f"\n🔄 調用 UpdateParasiteDrag()...")
vsp.UpdateParasiteDrag()
print(f"   完成")

print(f"\n再次檢查參數...")
for geom_id in geom_ids:
    geom_name = vsp.GetGeomName(geom_id)
    print(f"\n幾何: {geom_name}")

    # 獲取所有參數
    parm_ids = vsp.GetGeomParmIDs(geom_id)
    print(f"  總參數數量: {len(parm_ids)}")

    # 過濾包含 "parasit" 或 "drag" 的參數
    print(f"\n  包含 'parasit' 或 'drag' 的參數:")
    found_count = 0
    for parm_id in parm_ids:
        parm_name = vsp.GetParmName(parm_id)
        parm_container = vsp.GetParmContainer(parm_id)

        if "parasit" in parm_name.lower() or "drag" in parm_name.lower() or \
           "parasit" in parm_container.lower() or "drag" in parm_container.lower():
            val = vsp.GetParmVal(parm_id)
            print(f"    {parm_container}::{parm_name} = {val}")
            found_count += 1

    if found_count == 0:
        print(f"    （未找到相關參數）")

    # 嘗試特定參數
    print(f"\n  嘗試訪問特定參數:")
    test_params = [
        ("Parasite_Drag", "ParasiteDrag"),
        ("Parasite_Drag", "Parasite_Drag"),
        ("EqnType", "ParasiteDrag"),
        ("FFEqnType", "ParasiteDrag"),
        ("Include", "ParasiteDrag"),
    ]

    for parm_name, group_name in test_params:
        try:
            val = vsp.GetParmVal(geom_id, parm_name, group_name)
            print(f"    ✅ {group_name}::{parm_name} = {val}")
        except:
            print(f"    ❌ {group_name}::{parm_name} 不存在")

print("\n" + "="*80)
