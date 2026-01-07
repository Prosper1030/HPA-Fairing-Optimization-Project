"""執行最終模型生成器"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from optimization.generate_final_model import generate_final_model

gene = {
    'L': 2.5,
    'W_max': 0.60,
    'H_top_max': 0.95,
    'H_bot_max': 0.35,
    'N1': 0.5,
    'N2_top': 0.7,
    'N2_bot': 0.8,
    'X_max_pos': 0.25,
    'X_offset': 0.7,
}

output_file = "output/current/HPA_Fairing_FINAL.vsp3"

generate_final_model(gene, output_file, verbose=True)
