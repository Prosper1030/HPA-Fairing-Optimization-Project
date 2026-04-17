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
from pathlib import Path
import sys

from _bootstrap import ensure_src_path


project_root = os.fspath(ensure_src_path())

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
    write_batch_analysis_summary,
)


def _make_unique_case_name(path: Path, used_names: set[str]) -> str:
    stem = path.stem.strip() or "case"
    candidate = stem
    suffix = 2
    while candidate in used_names:
        candidate = f"{stem}_{suffix}"
        suffix += 1
    used_names.add(candidate)
    return candidate


def _analyze_single_case(
    *,
    gene_path: str,
    flow_conditions: dict,
    preset: str,
    backend: str,
    output_dir,
    report_config: dict,
    fill_missing_from_example: bool = False,
) -> tuple[dict, dict, dict, dict]:
    gene, gene_metadata = load_gene_file(
        gene_path,
        fill_missing_from_example=fill_missing_from_example,
        return_metadata=True,
    )
    analysis_result = analyze_gene(
        gene,
        flow_conditions=flow_conditions,
        preset=preset,
        backend=backend,
        include_geometry=True,
    )
    report_files = write_analysis_report_bundle(
        output_dir,
        gene,
        analysis_result,
        report_config,
        gene_metadata=gene_metadata,
    )
    return gene, gene_metadata, analysis_result, report_files


def main() -> int:
    parser = argparse.ArgumentParser(description="低速整流罩快速阻力分析工具")
    parser.add_argument("--gene", help="gene JSON 檔案路徑")
    parser.add_argument("--gene-dir", help="包含多個 gene JSON 的資料夾，會執行 batch 分析")
    parser.add_argument("--flow", help="流體條件 JSON 檔案路徑")
    parser.add_argument("--out", help="報告輸出目錄")
    parser.add_argument("--preset", choices=["none", "hpa"], help="限制 preset（預設讀 analysis_config）")
    parser.add_argument("--backend", choices=["fast_proxy"], help="分析 backend（目前只支援 fast_proxy）")
    parser.add_argument("--write-example-gene", metavar="PATH", help="寫出一份可直接修改的範例 gene JSON 後結束")
    parser.add_argument("--show-required-fields", action="store_true", help="列出 gene 必填欄位與建議範圍後結束")
    parser.add_argument("--fill-missing-from-example", action="store_true", help="若 gene 缺欄位，使用範例 gene 的預設值補齊")
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
        if not args.gene_dir:
            parser.error("必須提供 --gene 或 --gene-dir，或改用 --write-example-gene / --show-required-fields")

    if args.gene and args.gene_dir:
        parser.error("--gene 與 --gene-dir 只能擇一使用")

    defaults = load_analysis_config(os.path.join(project_root, "config", "analysis_config.json"))
    backend = args.backend or defaults["backend"]
    preset = args.preset or defaults["preset"]
    flow_path = args.flow or os.path.join(project_root, "config", "fluid_conditions.json")

    try:
        flow_conditions = load_flow_conditions(flow_path if os.path.exists(flow_path) else None)
        output_dir = prepare_analysis_output_dir(args.out, defaults["report"]["output_root"])

        if args.gene_dir:
            gene_dir = Path(args.gene_dir)
            if not gene_dir.exists() or not gene_dir.is_dir():
                raise AnalysisInputError(f"找不到 gene 資料夾: {gene_dir}")

            gene_files = sorted(path for path in gene_dir.iterdir() if path.is_file() and path.suffix.lower() == ".json")
            if not gene_files:
                raise AnalysisInputError(f"gene 資料夾內沒有 JSON 檔案: {gene_dir}")

            used_names: set[str] = set()
            entries: list[dict] = []

            for gene_file in gene_files:
                case_name = _make_unique_case_name(gene_file, used_names)
                case_output_dir = Path(output_dir) / case_name

                try:
                    _, gene_metadata, analysis_result, report_files = _analyze_single_case(
                        gene_path=str(gene_file),
                        flow_conditions=flow_conditions,
                        preset=preset,
                        backend=backend,
                        output_dir=case_output_dir,
                        report_config=defaults["report"],
                        fill_missing_from_example=args.fill_missing_from_example,
                    )
                    constraint_report = analysis_result["ConstraintReport"]
                    entries.append(
                        {
                            "Status": "ok",
                            "CaseName": case_name,
                            "GeneFile": str(gene_file),
                            "ReportDir": str(case_output_dir),
                            "Drag": float(analysis_result["Drag"]),
                            "Cd": float(analysis_result["Cd"]),
                            "Cd_viscous": float(analysis_result["Cd_viscous"]),
                            "Cd_pressure": float(analysis_result["Cd_pressure"]),
                            "Swet": float(analysis_result["Swet"]),
                            "LaminarFraction": float(analysis_result["LaminarFraction"]),
                            "RepresentativeTags": list(analysis_result.get("RepresentativeTags", [])),
                            "GeometryTraits": dict(analysis_result.get("GeometryTraits", {})),
                            "ConstraintState": constraint_report.get("all_pass") if constraint_report else None,
                            "FilledFields": gene_metadata.get("filled_fields", []),
                            "SummaryJson": report_files["summary_json"],
                            "SummaryMarkdown": report_files["summary_md"],
                        }
                    )
                except AnalysisInputError as exc:
                    entries.append(
                        {
                            "Status": "error",
                            "CaseName": case_name,
                            "GeneFile": str(gene_file),
                            "Error": str(exc),
                        }
                    )

            batch_files = write_batch_analysis_summary(output_dir, entries, preset=preset, backend=backend)
            success_count = sum(1 for entry in entries if entry["Status"] == "ok")
            failed_count = len(entries) - success_count

            print("低速整流罩 batch 分析完成")
            print(f"Backend: {backend}")
            print(f"Preset: {preset}")
            print(f"成功案例: {success_count}")
            print(f"失敗案例: {failed_count}")
            print(f"batch_summary.json: {batch_files['summary_json']}")
            print(f"batch_summary.md: {batch_files['summary_md']}")

            if success_count == 0:
                return 2
            return 0

        _, gene_metadata, analysis_result, report_files = _analyze_single_case(
            gene_path=args.gene,
            flow_conditions=flow_conditions,
            preset=preset,
            backend=backend,
            output_dir=output_dir,
            report_config=defaults["report"],
            fill_missing_from_example=args.fill_missing_from_example,
        )
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
    filled_fields = gene_metadata.get("filled_fields", [])
    if filled_fields:
        print(f"FilledFields: {', '.join(filled_fields)}")
    print(f"summary.json: {report_files['summary_json']}")
    print(f"summary.md: {report_files['summary_md']}")
    print(f"side_profile.png: {report_files['side_profile']}")
    print(f"drag_breakdown.png: {report_files['drag_breakdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
