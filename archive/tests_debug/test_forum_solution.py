"""
測試：根據論壇解法使用 FindParmGroup 設定 ParasiteDragProps
參考：OpenVSP Google Groups - Brandon Litherland 的解法
"""
import openvsp as vsp

print("="*80)
print("🧪 測試：論壇解法 - FindParmGroup")
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

# ========== 關鍵：使用 FindParmGroup 設定 ParasiteDragProps ==========
print(f"\n🔧 使用 FindParmGroup 設定 ParasiteDragProps...")

try:
    # 根據論壇建議，使用 FindParmGroup
    pd_props_group = vsp.FindParmGroup("ParasiteDragProps", geom_id)

    if pd_props_group:
        print(f"   ✅ 找到 ParasiteDragProps group: {pd_props_group}")

        # 列出這個 group 中的所有參數
        print(f"\n   ParasiteDragProps 中的參數:")
        parm_ids = vsp.GetGeomParmIDs(geom_id)
        for parm_id in parm_ids:
            if vsp.GetParmContainer(parm_id) == pd_props_group:
                parm_name = vsp.GetParmName(parm_id)
                val = vsp.GetParmVal(parm_id)
                print(f"      {parm_name} = {val}")

        # 設定 Form Factor 方程式類型為 Hoerner Streamlined Body
        ff_body_parm = vsp.FindParm(geom_id, "FFBodyEqnType", "ParasiteDragProps")
        if ff_body_parm:
            vsp.SetParmVal(ff_body_parm, 3.0)  # Hoerner Streamlined Body
            print(f"\n   ✅ 設定 FFBodyEqnType = 3.0 (Hoerner Streamlined Body)")

    else:
        print(f"   ❌ 無法找到 ParasiteDragProps group")

except Exception as e:
    print(f"   ⚠️ FindParmGroup 發生錯誤: {e}")

vsp.Update()

# ========== 執行 CompGeom ==========
print(f"\n📐 執行 CompGeom...")
vsp.SetAnalysisInputDefaults("CompGeom")
vsp.SetIntAnalysisInput("CompGeom", "GeomSet", [vsp.SET_ALL])
comp_res_id = vsp.ExecAnalysis("CompGeom")
wetted_area = vsp.GetDoubleResults(comp_res_id, "Wet_Area", 0)[0]
print(f"   濕面積: {wetted_area:.4f} m²")

# ========== 執行 ParasiteDrag（根據論壇完整流程）==========
print(f"\n🚀 執行 ParasiteDrag（論壇完整流程）...")

# 1. SetAnalysisInputDefaults
vsp.SetAnalysisInputDefaults("ParasiteDrag")

# 2. 設定分析參數
vsp.SetIntAnalysisInput("ParasiteDrag", "GeomSet", [vsp.SET_ALL])
print(f"   ✅ GeomSet: SET_ALL")

vsp.SetIntAnalysisInput("ParasiteDrag", "RefFlag", [0])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Sref", [1.0])
print(f"   ✅ RefFlag: 0, Sref: 1.0 m²")

vsp.SetIntAnalysisInput("ParasiteDrag", "AtmosType", [vsp.ATMOS_TYPE_US_STANDARD_1976])
print(f"   ✅ AtmosType: US_STANDARD_1976")

vsp.SetDoubleAnalysisInput("ParasiteDrag", "Vinf", [6.5])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Altitude", [0.0])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "DeltaTemp", [0.0])
print(f"   ✅ Vinf: 6.5 m/s, Altitude: 0.0 m")

vsp.SetIntAnalysisInput("ParasiteDrag", "LengthUnit", [vsp.LEN_M])
print(f"   ✅ LengthUnit: LEN_M")

vsp.SetIntAnalysisInput("ParasiteDrag", "LamCfEqnType", [vsp.CF_LAM_BLASIUS])
vsp.SetIntAnalysisInput("ParasiteDrag", "TurbCfEqnType", [vsp.CF_TURB_POWER_LAW_PRANDTL_LOW_RE])
print(f"   ✅ LamCfEqn: Blasius, TurbCfEqn: Power Law Prandtl Low Re")

# 3. 強制重算（論壇建議）
vsp.SetIntAnalysisInput("ParasiteDrag", "RecomputeGeom", [1])
print(f"   ✅ RecomputeGeom: 1")

# 4. 執行分析
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
        print(f"   ✅ 濕面積匹配 CompGeom 結果")
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
        print(f"\n🎉🎉🎉 問題解決！論壇解法有效！")
    elif diff_pct < 5.0:
        print(f"\n   ✅ 差異 < 5%，設置正確！")
    else:
        print(f"\n   ⚠️  仍有差異 ({diff_pct:.2f}%)")
        print(f"   提示：論壇建議檢查是否所有 Geom 都在正確的 Set 中")

except Exception as e:
    print(f"   ❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
