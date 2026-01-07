import openvsp as vsp

print("🔍 正在掃描目前的 OpenVSP API 功能庫...")
all_functions = dir(vsp)

# 搜尋跟 Analysis (分析) 有關的指令
analysis_funcs = [f for f in all_functions if "Analysis" in f]
geom_funcs = [f for f in all_functions if "Geom" in f]

print(f"\n📦 總指令數: {len(all_functions)}")

print("\n📊 分析相關指令 (Analysis):")
if analysis_funcs:
    for f in analysis_funcs:
        print(f"   - {f}")
else:
    print("   ❌ 找不到任何 Analysis 指令 (這證實了分析模組遺失)")

print("\n📐 幾何相關指令 (Geom) [前 5 個]:")
for f in geom_funcs[:5]:
    print(f"   - {f}")

print("\n💡 結論：")
if not analysis_funcs:
    print("你的 Python 環境只有『畫圖』功能，『計算』功能在移植過程中遺失了。")
    print("這就是為什麼我們必須用剛剛那個『純數學版』程式自己算的原因。")
else:
    print("噢！其實有指令！可能是我們拼字拼錯了，請告訴我上面列出了什麼。")