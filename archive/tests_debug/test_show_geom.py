"""
測試：明確將幾何設為 Shown 並使用 SET_SHOWN
根據論壇案例 2：PD 只算 Shown Set 中的 Geom
"""
import openvsp as vsp

print("="*80)
print("🧪 測試：明確設定 Geom 為 Shown")
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

# ========== 檢查幾何的 Set 成員資格 ==========
print(f"\n🔍 檢查幾何的 Set 成員資格...")

# 檢查幾何是否在各個 Set 中
sets_to_check = [
    ("SET_ALL", vsp.SET_ALL),
    ("SET_SHOWN", vsp.SET_SHOWN),
    ("SET_NOT_SHOWN", vsp.SET_NOT_SHOWN),
]

for set_name, set_index in sets_to_check:
    # 使用 GetSetFlag 檢查幾何是否在這個 Set 中
    try:
        in_set = vsp.GetSetFlag(geom_id, set_index)
        print(f"   {set_name} ({set_index}): {'✅ 在' if in_set else '❌ 不在'}")
    except Exception as e:
        print(f"   {set_name} ({set_index}): ⚠️ 無法檢查 ({e})")

# ========== 明確將幾何加入 SET_SHOWN ==========
print(f"\n🔧 明確設定幾何為 Shown...")

try:
    # 將幾何加入 SET_SHOWN
    vsp.SetSetFlag(geom_id, vsp.SET_SHOWN, 1)
    print(f"   ✅ 已將幾何加入 SET_SHOWN")

    # 從 SET_NOT_SHOWN 移除（如果在裡面）
    vsp.SetSetFlag(geom_id, vsp.SET_NOT_SHOWN, 0)
    print(f"   ✅ 已從 SET_NOT_SHOWN 移除")

    # 驗證
    in_shown = vsp.GetSetFlag(geom_id, vsp.SET_SHOWN)
    print(f"   驗證：在 SET_SHOWN = {in_shown}")

except Exception as e:
    print(f"   ⚠️ 設定失敗: {e}")

vsp.Update()

# ========== 執行 CompGeom ==========
print(f"\n📐 執行 CompGeom (使用 SET_SHOWN)...")
vsp.SetAnalysisInputDefaults("CompGeom")
vsp.SetIntAnalysisInput("CompGeom", "GeomSet", [vsp.SET_SHOWN])
comp_res_id = vsp.ExecAnalysis("CompGeom")
wetted_area = vsp.GetDoubleResults(comp_res_id, "Wet_Area", 0)[0]
print(f"   濕面積: {wetted_area:.4f} m²")

# ========== 執行 ParasiteDrag（使用 SET_SHOWN）==========
print(f"\n🚀 執行 ParasiteDrag (使用 SET_SHOWN)...")

vsp.SetAnalysisInputDefaults("ParasiteDrag")

# ⭐⭐⭐ 關鍵：使用 SET_SHOWN 而不是 SET_ALL
vsp.SetIntAnalysisInput("ParasiteDrag", "GeomSet", [vsp.SET_SHOWN])
print(f"   ✅ GeomSet: SET_SHOWN")

vsp.SetIntAnalysisInput("ParasiteDrag", "RefFlag", [0])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Sref", [1.0])
vsp.SetIntAnalysisInput("ParasiteDrag", "AtmosType", [vsp.ATMOS_TYPE_US_STANDARD_1976])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Vinf", [6.5])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Altitude", [0.0])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "DeltaTemp", [0.0])
vsp.SetIntAnalysisInput("ParasiteDrag", "LengthUnit", [vsp.LEN_M])
vsp.SetIntAnalysisInput("ParasiteDrag", "LamCfEqnType", [vsp.CF_LAM_BLASIUS])
vsp.SetIntAnalysisInput("ParasiteDrag", "TurbCfEqnType", [vsp.CF_TURB_POWER_LAW_PRANDTL_LOW_RE])
vsp.SetIntAnalysisInput("ParasiteDrag", "RecomputeGeom", [1])

pd_res_id = vsp.ExecAnalysis("ParasiteDrag")

# ========== 提取結果 ==========
print(f"\n📊 提取結果...")
try:
    cd_total = vsp.GetDoubleResults(pd_res_id, "Total_CD_Total", 0)[0]
    swet_result = vsp.GetDoubleResults(pd_res_id, "Comp_Swet", 0)[0]

    print(f"   CD: {cd_total:.6f}")
    print(f"   濕面積（從 ParasiteDrag）: {swet_result:.4f} m²")

    # 檢查濕面積是否匹配
    wetted_area_match = abs(swet_result - wetted_area) < 0.01
    if wetted_area_match:
        print(f"   ✅ 濕面積匹配 CompGeom 結果！")
    else:
        print(f"   ⚠️  濕面積不匹配！CompGeom: {wetted_area:.4f}, ParasiteDrag: {swet_result:.4f}")

    print(f"\n💡 與 GUI 對比：")
    print(f"   GUI CD: 0.02045")
    print(f"   API CD: {cd_total:.6f}")

    diff = abs(cd_total - 0.02045)
    diff_pct = (diff / 0.02045) * 100
    print(f"   絕對差異: {diff:.6f}")
    print(f"   相對差異: {diff_pct:.2f}%")

    if diff_pct < 2.0:
        print(f"\n   ✅✅✅ 完美匹配！差異 < 2%")
        print(f"\n🎉🎉🎉 問題解決！使用 SET_SHOWN 是關鍵！")
    elif diff_pct < 5.0:
        print(f"\n   ✅ 差異 < 5%，設置正確！")
    else:
        print(f"\n   ⚠️  仍有差異 ({diff_pct:.2f}%)")

except Exception as e:
    print(f"   ❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
