import os

# 這是 pip 安裝的目標路徑
target_path = r"D:\文件\大四\整流罩\vsp_env\Lib\site-packages\openvsp"

print(f"📂 正在檢查目錄：\n{target_path}")
print("-" * 50)

if not os.path.exists(target_path):
    print("❌ 錯誤：找不到這個資料夾！pip 可能沒有正確安裝到這裡。")
else:
    files = os.listdir(target_path)
    files.sort() # 排個序比較好找

    # 我們要找的關鍵嫌疑犯
    important_files = ["_vsp.pyd", "vsp.py", "vcruntime140_1.dll", "vcomp140.dll"]
    
    found_dlls = 0
    
    for f in files:
        # 特別標記出 DLL 和核心檔案
        if f.endswith(".dll"):
            print(f" ✅ [DLL] {f}")
            found_dlls += 1
        elif f == "_vsp.pyd":
            print(f" 🌟 [核心] {f} (這是 Python 的大腦)")
        elif f == "vsp.py":
            print(f" 📄 [封裝] {f}")
        else:
            print(f" - {f}")

    print("-" * 50)
    print(f"總共發現 {len(files)} 個檔案。")
    print(f"其中包含 {found_dlls} 個 DLL 檔。")