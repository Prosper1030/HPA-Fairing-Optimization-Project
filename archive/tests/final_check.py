import openvsp as vsp

# 以前這行會報錯，現在它應該要秒過！
print(f"🎉 恭喜！OpenVSP 3.42.3 安裝圓滿成功！")
print(f"偵測到的版本: {vsp.GetVSPVersion()}")

# 測試核心指令
vsp.VSPRenew()
print("VSP 核心功能正常，隨時可以開始設計飛機！")