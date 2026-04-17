"""
User-facing CLI for preparing SU2 shortlist validation bundles.

This command does not run SU2. It collects one or more shortlisted fairing
designs, evaluates them with the fast proxy backend, and writes a reproducible
SU2 work package for each case.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from _bootstrap import ensure_src_path


project_root = os.fspath(ensure_src_path())

from analysis import (
    AnalysisInputError,
    load_analysis_config,
    prepare_shortlist_validation_package,
)


def _load_json(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_gene_candidate(gene_path: str | Path) -> dict:
    path = Path(gene_path)
    if not path.exists():
        raise AnalysisInputError(f"找不到 gene 檔案: {path}")
    try:
        payload = _load_json(path)
    except json.JSONDecodeError as exc:
        raise AnalysisInputError(f"gene JSON 格式錯誤: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise AnalysisInputError(f"gene 檔案必須是 JSON 物件: {path}")
    return {
        "name": path.stem,
        "GeneFile": str(path),
        "gene": payload,
    }


def _load_best_gene_candidate(best_gene_path: str | Path) -> dict:
    path = Path(best_gene_path)
    if not path.exists():
        raise AnalysisInputError(f"找不到 best_gene 檔案: {path}")
    try:
        payload = _load_json(path)
    except json.JSONDecodeError as exc:
        raise AnalysisInputError(f"best_gene JSON 格式錯誤: {exc.msg}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("gene"), dict):
        raise AnalysisInputError(f"best_gene 檔案格式錯誤，缺少 gene 區塊: {path}")
    return {
        "name": path.stem,
        "GeneFile": str(path),
        "gene": payload["gene"],
        "Notes": {
            "fitness": payload.get("fitness"),
            "generation": payload.get("generation"),
            "timestamp": payload.get("timestamp"),
        },
    }


def _load_gene_dir_candidates(gene_dir: str | Path) -> list[dict]:
    path = Path(gene_dir)
    if not path.exists() or not path.is_dir():
        raise AnalysisInputError(f"找不到 gene 資料夾: {path}")

    gene_files = sorted(entry for entry in path.iterdir() if entry.is_file() and entry.suffix.lower() == ".json")
    if not gene_files:
        raise AnalysisInputError(f"gene 資料夾內沒有 JSON 檔案: {path}")

    return [_load_gene_candidate(gene_file) for gene_file in gene_files]


def _load_batch_summary_candidates(batch_summary_path: str | Path, top: int | None) -> list[dict]:
    path = Path(batch_summary_path)
    if not path.exists():
        raise AnalysisInputError(f"找不到 batch_summary 檔案: {path}")

    try:
        payload = _load_json(path)
    except json.JSONDecodeError as exc:
        raise AnalysisInputError(f"batch_summary JSON 格式錯誤: {exc.msg}") from exc

    ranked_cases = payload.get("RankedCases")
    if not isinstance(ranked_cases, list):
        raise AnalysisInputError(f"batch_summary 缺少 RankedCases 陣列: {path}")

    if top is not None:
        ranked_cases = ranked_cases[:top]
    if not ranked_cases:
        raise AnalysisInputError("batch_summary 沒有可用的成功案例")

    candidates: list[dict] = []
    for entry in ranked_cases:
        if not isinstance(entry, dict):
            raise AnalysisInputError("RankedCases 內每筆資料都必須是 JSON 物件")
        gene_file = entry.get("GeneFile")
        if not gene_file:
            raise AnalysisInputError("RankedCases 缺少 GeneFile 欄位")
        candidate = _load_gene_candidate(gene_file)
        candidate["name"] = entry.get("CaseName") or candidate["name"]
        candidate["Notes"] = {
            "rank": entry.get("Rank"),
            "drag": entry.get("Drag"),
            "cd": entry.get("Cd"),
            "source_batch_summary": str(path),
        }
        candidates.append(candidate)
    return candidates


def _normalize_geometry_exports(raw_exports: list[str]) -> list[str] | None:
    if not raw_exports:
        return None
    exports: list[str] = []
    for item in raw_exports:
        token = item.strip().lower()
        if not token:
            continue
        if token == "html":
            token = "preview"
        if token not in exports:
            exports.append(token)
    return exports or None


def _first_existing_prepared_file(manifest: dict, key: str) -> str | None:
    for case in manifest.get("Cases", []):
        prepared = case.get("PreparedFiles", {})
        path = prepared.get(key)
        if path:
            return str(path)
    return None


def _collect_candidates(args) -> list[dict]:
    candidates: list[dict] = []

    for gene_path in args.gene:
        candidates.append(_load_gene_candidate(gene_path))
    for gene_dir in args.gene_dir:
        candidates.extend(_load_gene_dir_candidates(gene_dir))
    for best_gene_path in args.best_gene:
        candidates.append(_load_best_gene_candidate(best_gene_path))
    for batch_summary_path in args.batch_summary:
        candidates.extend(_load_batch_summary_candidates(batch_summary_path, args.top))

    if not candidates:
        raise AnalysisInputError(
            "至少要提供一個來源：--gene、--gene-dir、--best-gene 或 --batch-summary"
        )
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="準備 SU2 shortlist 驗證工作包")
    parser.add_argument("--gene", action="append", default=[], help="單一 gene JSON 檔案，可重複提供")
    parser.add_argument("--gene-dir", action="append", default=[], help="包含多個 gene JSON 的資料夾，可重複提供")
    parser.add_argument("--best-gene", action="append", default=[], help="GA 產出的 best_gene.json，可重複提供")
    parser.add_argument("--batch-summary", action="append", default=[], help="analyze_fairing.py 產出的 batch_summary.json，可重複提供")
    parser.add_argument("--top", type=int, help="搭配 --batch-summary 使用，只取前 N 名")
    parser.add_argument("--flow", help="流體條件 JSON 檔案路徑")
    parser.add_argument("--out", required=True, help="SU2 工作包輸出目錄")
    parser.add_argument("--preset", choices=["none", "hpa"], help="限制 preset（預設讀 analysis_config）")
    parser.add_argument("--backend", choices=["su2"], default="su2", help="高保真 backend（目前只支援 su2）")
    parser.add_argument(
        "--mesh-mode",
        choices=["manual_3d", "axisymmetric_2d", "gmsh_3d"],
        default="manual_3d",
        help="mesh 準備模式：manual_3d 只出工作包；axisymmetric_2d / gmsh_3d 會自動產生可跑的 benchmark mesh",
    )
    parser.add_argument(
        "--geometry-export",
        action="append",
        default=[],
        help="匯出格式（可重複）。可用：preview、stl、obj、step、brep、html(等同 preview)；未指定時預設產出 preview + stl + obj",
    )
    parser.add_argument(
        "--geometry-section-count",
        type=int,
        default=64,
        help="geometry preview / mesh 的軸向截面數量（預設 64）",
    )
    parser.add_argument(
        "--geometry-section-points",
        type=int,
        default=40,
        help="每個截面輪廓的點數（預設 40）",
    )
    parser.add_argument("--fill-missing-from-example", action="store_true", help="若 gene 缺欄位，使用範例 gene 預設值補齊")
    args = parser.parse_args()

    if args.top is not None and args.top <= 0:
        parser.error("--top 必須是正整數")

    defaults = load_analysis_config(os.path.join(project_root, "config", "analysis_config.json"))
    preset = args.preset or defaults["preset"]
    flow_path = args.flow or os.path.join(project_root, "config", "fluid_conditions.json")

    try:
        candidates = _collect_candidates(args)
        manifest = prepare_shortlist_validation_package(
            candidates,
            output_dir=args.out,
            backend=args.backend,
            flow_conditions=flow_path if os.path.exists(flow_path) else None,
            preset=preset,
            fill_missing_from_example=args.fill_missing_from_example,
            mesh_mode=args.mesh_mode,
            geometry_exports=_normalize_geometry_exports(args.geometry_export),
            geometry_section_count=args.geometry_section_count,
            geometry_section_points=args.geometry_section_points,
        )
    except AnalysisInputError as exc:
        print(f"錯誤: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"準備 SU2 工作包失敗: {exc}", file=sys.stderr)
        return 1

    print("SU2 shortlist 工作包準備完成")
    print(f"Backend: {manifest['Backend']}")
    print(f"Preset: {manifest['Preset']}")
    print(f"MeshMode: {manifest['MeshMode']}")
    print(f"CaseCount: {manifest['CaseCount']}")
    print(f"validation_manifest.json: {manifest['ManifestFiles']['json']}")
    print(f"validation_manifest.md: {manifest['ManifestFiles']['markdown']}")
    print(f"run_all_su2_cases.sh: {manifest['RunScript']}")
    preview_path = _first_existing_prepared_file(manifest, "geometry_preview_html")
    obj_path = _first_existing_prepared_file(manifest, "geometry_obj")
    stl_path = _first_existing_prepared_file(manifest, "geometry_stl")
    if preview_path:
        print(f"geometry_preview.html: {preview_path}")
    if obj_path:
        print(f"fairing_surface.obj: {obj_path}")
    if stl_path:
        print(f"fairing_surface.stl: {stl_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
