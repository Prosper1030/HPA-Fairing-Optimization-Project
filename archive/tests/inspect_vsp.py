import openvsp as vsp

print("🚀 OpenVSP 參數診斷程式啟動...")

# 1. 建立一個乾淨的機身
vsp.ClearVSPModel()
fuse_id = vsp.AddGeom("FUSELAGE")
vsp.SetGeomName(fuse_id, "Test_Fuselage")

# 2. 抓取第 0 個截面 (通常是機頭)
xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
num_xsecs = vsp.GetNumXSec(xsec_surf)
print(f"📦 初始截面總數: {num_xsecs}")

# 3. 檢查每一個截面的「類型」與「參數」
for i in range(num_xsecs):
    print(f"\n--- 🔍 檢查第 {i} 個截面 ---")
    xsec = vsp.GetXSec(xsec_surf, i)
    
    # 讀取形狀類型 (0=Point, 1=Circle, 2=Ellipse...)
    # 註：不同版本 VSP 代碼可能不同，我們嘗試讀取
    try:
        shape_type = vsp.GetXSecShape(xsec)
        print(f"   [形狀類型代碼]: {shape_type} (預測: 0=Point, 1=Circle, 2=Ellipse)")
    except:
        print("   [形狀類型]: 無法讀取")

    # 列出所有可用的參數名稱 (這是最關鍵的一步！)
    print("   [可用參數列表]:")
    parm_list = vsp.GetXSecParmIDs(xsec)
    
    found_params = []
    for p_id in parm_list:
        p_name = vsp.GetParmName(p_id)
        # 過濾掉一些內部雜訊，只看我們關心的
        if "Loc" in p_name or "Width" in p_name or "Height" in p_name or "X" == p_name:
            val = vsp.GetParmVal(p_id)
            print(f"      👉 {p_name} (目前數值: {val})")
            found_params.append(p_name)
            
    if not found_params:
        print("      (沒有找到類似 Width/Height/Loc 的參數，請檢查完整列表)")
        # 如果上面過濾太嚴格，這裡印出前 10 個讓你看
        for k, p_id in enumerate(parm_list[:10]):
            print(f"      (Raw): {vsp.GetParmName(p_id)}")

print("\n✅ 診斷完成！請複製以上內容給我。")