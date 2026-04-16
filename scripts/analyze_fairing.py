"""
User-facing CLI for low-speed fairing drag analysis.

This entry point uses the fast proxy backend only. OpenVSP remains available in
the repository for legacy comparisons, but it is intentionally not exposed as a
normal day-to-day workflow here.
"""

from __future__ import annotations

import argparse
import json
import os
import sys


project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(project_root, "src"))

from analysis.fairing_analysis import (
    AnalysisInputError,
    analyze_gene,
    format_required_gene_fields,
    get_example_gene,
    load_analysis_config,
    load_flow_conditions,
    load_gene_file,
    prepare_analysis_output_dir,
    write_analysis_report_bundle,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="低速整流罩快速阻力分析工具")
    parser.add_argument("--gene", help="gene JSON 檔案路徑")
    parser.add_argument("--flow", help="流體條件 JSON 檔案路徑")
    parser.add_argument("--out", help="報告輸出目錄")
    parser.add_argument("--preset", choices=["none", "hpa"], help="限制 preset（預設讀 analysis_config）")
    parser.add_argument("--backend", choices=["fast_proxy"], help="分析 backend（目前只支援 fast_proxy）")
    parser.add_argument("--write-example-gene", metavar="PATH", help="寫出一份可直接修改的範例 gene JSON 後結束")
    parser.add_argument("--show-required-fields", action="store_true", help="列出 gene 必填欄位與建議範圍後結束")
    args = parser.parse_args()

    if args.write_example_gene:
        output_path = args.write_example_gene
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(get_example_gene(), handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        print(f"已寫出範例 gene: {output_path}")
        print("接著可用 `python scripts/analyze_fairing.py --gene <path>` 執行分析。")
        return 0

    if args.show_required_fields:
        print(format_required_gene_fields())
        print("")
        print("可用 `python scripts/analyze_fairing.py --write-example-gene example_gene.json` 產生範例檔。")
        return 0

    if not args.gene:
        parser.error("必須提供 --gene，或改用 --write-example-gene / --show-required-fields")

    defaults = load_analysis_config(os.path.join(project_root, "config", "analysis_config.json"))
    backend = args.backend or defaults["backend"]
    preset = args.preset or defaults["preset"]
    flow_path = args.flow or os.path.join(project_root, "config", "fluid_conditions.json")

    try:
        gene = load_gene_file(args.gene)
        flow_conditions = load_flow_conditions(flow_path if os.path.exists(flow_path) else None)
        analysis_result = analyze_gene(
            gene,
            flow_conditions=flow_conditions,
            preset=preset,
            backend=backend,
            include_geometry=True,
        )
        output_dir = prepare_analysis_output_dir(args.out, defaults["report"]["output_root"])
        report_files = write_analysis_report_bundle(output_dir, gene, analysis_result, defaults["report"])
    except AnalysisInputError as exc:
        print(f"錯誤: {exc}", file=sys.stderr)
        print(
            "提示: 可先用 `python scripts/analyze_fairing.py --write-example-gene example_gene.json` 產生範例檔。",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(f"分析失敗: {exc}", file=sys.stderr)
        return 1

    constraint_report = analysis_result["ConstraintReport"]
    print("低速整流罩分析完成")
    print(f"Backend: {analysis_result['Backend']}")
    print(f"Preset: {analysis_result['PresetUsed']}")
    print(f"Drag: {analysis_result['Drag']:.4f} N")
    print(f"Cd: {analysis_result['Cd']:.6f}")
    print(f"Swet: {analysis_result['Swet']:.3f} m^2")
    print(f"LaminarFraction: {analysis_result['LaminarFraction']:.3f}")
    if constraint_report:
        print(f"HPA constraints: {'PASS' if constraint_report['all_pass'] else 'FAIL'}")
    print(f"summary.json: {report_files['summary_json']}")
    print(f"summary.md: {report_files['summary_md']}")
    print(f"side_profile.png: {report_files['side_profile']}")
    print(f"drag_breakdown.png: {report_files['drag_breakdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
