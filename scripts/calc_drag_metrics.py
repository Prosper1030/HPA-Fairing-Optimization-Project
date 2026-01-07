import csv
import os

# --- 1. 物理環境設定 ---
# 這些數值必須跟你 OpenVSP 設定的一樣，才能還原真實力量
V = 6.5           # 飛行速度 (m/s)
rho = 1.1839      # 空氣密度 (kg/m^3) @ 25°C
q = 0.5 * rho * (V ** 2)  # 動壓 (Dynamic Pressure), 約 25.01 Pa

print(f"🚀 OpenVSP 阻力數據分析工具 (完整版)")
print(f"   環境條件: V = {V} m/s, Rho = {rho} kg/m^3, q = {q:.4f} Pa")
print("=" * 115)
# 修改表頭，加入 Cd 欄位
print(f"{'設計名稱':<25} | {'阻力面積 (Cd*A)':<18} | {'阻力係數 (Cd)':<15} | {'真實阻力 (N)':<15} | {'濕面積 (S_wet)':<15}")
print(f"{'':<25} | {'(m^2)':<18} | {'(無單位)':<15} | {'(Newton)':<15} | {'(m^2)':<15}")
print("-" * 115)

# 自動搜尋目錄下所有 ParasiteBuildUp 檔案
files = [f for f in os.listdir('.') if f.endswith('_ParasiteBuildUp.csv')]
results = []

for filename in files:
    name = filename.replace('_ParasiteBuildUp.csv', '')
    
    try:
        with open(filename, 'r', newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)
            
            # --- 智慧欄位偵測 ---
            header_idx = -1
            f_idx = -1       # 阻力面積 (f) 的欄位索引
            swet_idx = -1    # 濕面積 (S_wet) 的欄位索引
            cd_idx = -1      # 阻力係數 (Cd) 的欄位索引
            
            for i, row in enumerate(rows):
                # 轉小寫搜尋關鍵字，去除多餘空白
                row_lower = [c.lower().strip() for c in row]
                
                # 尋找含有 "f" (CdA) 或 "Cd" 的標題列
                # OpenVSP 的標題通常是: Component Name, S_wet, ..., f (ft^2), Cd, ...
                if "f (ft^2)" in row or "f" in row_lower or "cd" in row_lower:
                    header_idx = i
                    # 抓出各個欄位的索引位置
                    for idx, col in enumerate(row):
                        c_str = col.lower()
                        # 找 f (排除 FF 這種字眼)
                        if "f" in c_str and "ff" not in c_str:
                            f_idx = idx
                        # 找 S_wet
                        if "s_wet" in c_str:
                            swet_idx = idx
                        # 找 Cd (排除 Cda 或 Code 這種字眼)
                        if "cd" in c_str and "cda" not in c_str:
                            cd_idx = idx
                    continue
                
                # 在標題列之後，尋找數據列
                # 通常是含有 "Total" 的總和列，或是跟檔名一樣的主組件列
                if header_idx != -1 and i > header_idx:
                    # 判斷是否為有效數據行
                    is_total_row = "Total" in row[0] or "Totals" in row[0]
                    is_component_row = name in row[0]
                    
                    if is_total_row or is_component_row:
                        try:
                            # 讀取 CdA (f值)
                            CdA = float(row[f_idx])
                            
                            # 讀取濕面積
                            S_wet = float(row[swet_idx]) if swet_idx != -1 else 0.0
                            
                            # 讀取 Cd
                            # 如果找不到 Cd 欄位，嘗試用 CdA / S_wet 反推 (防呆)
                            if cd_idx != -1:
                                Cd = float(row[cd_idx])
                            else:
                                Cd = CdA / S_wet if S_wet > 0 else 0.0

                            # 計算真實阻力 D = q * CdA
                            Drag = q * CdA
                            
                            # 存入結果
                            results.append({
                                'name': name,
                                'CdA': CdA,
                                'Cd': Cd,
                                'Drag': Drag,
                                'Swet': S_wet
                            })
                            
                            # 讀到一筆有效數據後就跳出，避免重複讀取 (例如同時讀到 Component 和 Total)
                            break 
                        except (ValueError, IndexError):
                            continue

    except Exception as e:
        print(f"❌ 讀取 {filename} 失敗: {e}")

# --- 排序並輸出 ---
# 依照真實阻力 (Drag) 由小到大排序
results.sort(key=lambda x: x['Drag'])

for res in results:
    print(f"{res['name']:<25} | {res['CdA']:<18.6f} | {res['Cd']:<15.6f} | {res['Drag']:<15.5f} | {res['Swet']:<15.4f}")

print("-" * 115)

if results:
    best = results[0]
    worst = results[-1]
    diff = worst['Drag'] - best['Drag']
    print(f"🏆 最佳設計: {best['name']}")
    print(f"   它的 Cd 為 {best['Cd']:.6f}，真實阻力為 {best['Drag']:.5f} N")
    print(f"   比最差的設計省了 {diff:.4f} 牛頓")
else:
    print("⚠️ 找不到任何有效的數據，請確認 _ParasiteBuildUp.csv 檔案是否存在。")