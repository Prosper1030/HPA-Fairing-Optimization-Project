"""
Generate a family-coverage batch of representative low-speed fairing genes.

This command writes a curated set of archetype gene JSON files, runs the fast
proxy analysis for each one, and emits the same batch_summary bundle shape that
`analyze_fairing.py --gene-dir ...` produces. The output can be fed directly
into `run_su2_mesh_study.py --batch-summary ... --representative-study`.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path

from _bootstrap import ensure_src_path


project_root = os.fspath(ensure_src_path())

from analysis import (
    analyze_gene,
    get_representative_gene_cases,
    load_analysis_config,
    load_flow_conditions,
    write_analysis_report_bundle,
    write_batch_analysis_summary,
)


def _write_gene_json(path: Path, gene: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(gene, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _build_manifest_markdown(manifest: dict) -> str:
    lines = [
        "# Representative Gene Batch",
        "",
        f"- GeneratedAt: {manifest['GeneratedAt']}",
        f"- Preset: {manifest['Preset']}",
        f"- TotalCases: {manifest['TotalCases']}",
        f"- CoveredTags: {', '.join(manifest['CoveredTags'])}",
        "",
    ]

    for entry in manifest["Cases"]:
        lines.extend(
            [
                f"## {entry['CaseName']}",
                "",
                f"- Description: {entry['Description']}",
                f"- TargetTags: {', '.join(entry['TargetTags']) or 'none'}",
                f"- AchievedTags: {', '.join(entry['AchievedTags']) or 'none'}",
                f"- GeneFile: {entry['GeneFile']}",
                f"- ReportDir: {entry['ReportDir']}",
                "",
            ]
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="產生可直接拿去做 SU2 驗證的代表性整流罩 gene 批次")
    parser.add_argument("--out", required=True, help="輸出目錄")
    parser.add_argument("--flow", help="流體條件 JSON 檔案路徑")
    parser.add_argument("--preset", choices=["none", "hpa"], help="限制 preset（預設讀 analysis_config）")
    args = parser.parse_args()

    defaults = load_analysis_config(os.path.join(project_root, "config", "analysis_config.json"))
    preset = args.preset or defaults["preset"]
    flow_path = args.flow or os.path.join(project_root, "config", "fluid_conditions.json")
    flow_conditions = load_flow_conditions(flow_path if os.path.exists(flow_path) else None)

    output_dir = Path(args.out)
    genes_dir = output_dir / "genes"
    cases_dir = output_dir / "cases"
    output_dir.mkdir(parents=True, exist_ok=True)
    genes_dir.mkdir(parents=True, exist_ok=True)
    cases_dir.mkdir(parents=True, exist_ok=True)

    entries: list[dict] = []
    manifest_cases: list[dict] = []
    covered_tags: set[str] = set()

    for case in get_representative_gene_cases():
        case_name = case["CaseName"]
        gene = case["Gene"]
        gene_path = genes_dir / f"{case_name}.json"
        report_dir = cases_dir / case_name

        _write_gene_json(gene_path, gene)

        analysis = analyze_gene(
            gene,
            flow_conditions=flow_conditions,
            preset=preset,
            backend="fast_proxy",
            include_geometry=True,
        )
        report_files = write_analysis_report_bundle(
            report_dir,
            gene,
            analysis,
            defaults["report"],
            gene_metadata={"filled_fields": []},
        )
        achieved_tags = list(analysis.get("RepresentativeTags", []))
        covered_tags.update(achieved_tags)
        constraint_report = analysis["ConstraintReport"]

        entries.append(
            {
                "Status": "ok",
                "CaseName": case_name,
                "GeneFile": str(gene_path),
                "ReportDir": str(report_dir),
                "Drag": float(analysis["Drag"]),
                "Cd": float(analysis["Cd"]),
                "Cd_viscous": float(analysis["Cd_viscous"]),
                "Cd_pressure": float(analysis["Cd_pressure"]),
                "Swet": float(analysis["Swet"]),
                "LaminarFraction": float(analysis["LaminarFraction"]),
                "RepresentativeTags": achieved_tags,
                "GeometryTraits": dict(analysis.get("GeometryTraits", {})),
                "ConstraintState": constraint_report.get("all_pass") if constraint_report else None,
                "FilledFields": [],
                "SummaryJson": report_files["summary_json"],
                "SummaryMarkdown": report_files["summary_md"],
                "TargetTags": list(case["TargetTags"]),
                "Description": case["Description"],
            }
        )
        manifest_cases.append(
            {
                "CaseName": case_name,
                "Description": case["Description"],
                "TargetTags": list(case["TargetTags"]),
                "AchievedTags": achieved_tags,
                "GeneFile": str(gene_path),
                "ReportDir": str(report_dir),
            }
        )

    batch_files = write_batch_analysis_summary(output_dir, entries, preset=preset, backend="fast_proxy")
    manifest = {
        "GeneratedAt": datetime.now().isoformat(),
        "Preset": preset,
        "TotalCases": len(manifest_cases),
        "CoveredTags": sorted(covered_tags),
        "Cases": manifest_cases,
        "BatchSummary": batch_files,
    }

    manifest_json_path = output_dir / "representative_manifest.json"
    manifest_md_path = output_dir / "representative_manifest.md"
    with open(manifest_json_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    manifest_md_path.write_text(_build_manifest_markdown(manifest), encoding="utf-8")

    print("代表性整流罩 gene 批次已產生")
    print(f"Preset: {preset}")
    print(f"Cases: {len(manifest_cases)}")
    print(f"CoveredTags: {', '.join(sorted(covered_tags))}")
    print(f"genes/: {genes_dir}")
    print(f"batch_summary.json: {batch_files['summary_json']}")
    print(f"representative_manifest.json: {manifest_json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
