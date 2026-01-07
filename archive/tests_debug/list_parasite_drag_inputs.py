"""
列出 ParasiteDrag 分析的所有輸入參數
"""
import openvsp as vsp

print("="*80)
print("🔍 ParasiteDrag 分析輸入參數列表")
print("="*80)

# 載入模型
test_file = "output/Fixed_Angles_Test.vsp3"
vsp.ClearVSPModel()
vsp.ReadVSPFile(test_file)
vsp.Update()

# 設置默認值
vsp.SetAnalysisInputDefaults("ParasiteDrag")

# 列出所有輸入
print("\n嘗試獲取常見的 ParasiteDrag 輸入參數:\n")

common_inputs = [
    ("Vinf", "double"),
    ("Altitude", "double"),
    ("DeltaTemp", "double"),
    ("Density", "double"),
    ("Temperature", "double"),
    ("Pressure", "double"),
    ("KineVisc", "double"),
    ("Sref", "double"),
    ("GeomSet", "int"),
    ("LengthUnit", "int"),
    ("FreestreamPropChoice", "int"),
    ("AtmosType", "int"),
    ("LamCfEqnType", "int"),
    ("TurbCfEqnType", "int"),
    ("FFBodyEqnType", "int"),
    ("FFWingEqnType", "int"),
]

for param_name, param_type in common_inputs:
    try:
        if param_type == "double":
            value = vsp.GetDoubleAnalysisInput("ParasiteDrag", param_name)
            print(f"  {param_name} ({param_type}): {value}")
        elif param_type == "int":
            value = vsp.GetIntAnalysisInput("ParasiteDrag", param_name)
            print(f"  {param_name} ({param_type}): {value}")
        elif param_type == "string":
            value = vsp.GetStringAnalysisInput("ParasiteDrag", param_name)
            print(f"  {param_name} ({param_type}): {value}")
    except Exception as e:
        print(f"  {param_name} ({param_type}): ❌ 不存在或錯誤")

print("\n" + "="*80)
print("✅ 完成！")
print("="*80)
