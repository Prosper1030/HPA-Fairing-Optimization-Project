"""
Launch an unattended SU2 verification batch for the fairing family.

This wrapper exists for one purpose: turn the current SU2 workflow into a
repeatable overnight run that generates a representative case set, executes a
curated mesh-study batch, and leaves behind a single manifest plus per-step
logs that can be reviewed the next day.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

from _bootstrap import PROJECT_ROOT, ensure_src_path


project_root = os.fspath(ensure_src_path())

from analysis import load_analysis_config


ANCHOR_CASES = (
    "slender_forward_conservative",
    "mid_pack_example",
    "shortfat_aft_aggressive",
)

DEFAULT_CASE_SET = "anchor3"
DEFAULT_PROFILES = ("baseline",)


def _default_ranks() -> int:
    cpu_count = os.cpu_count() or 1
    return max(1, min(4, cpu_count))


def _stringify_command(command: list[str]) -> str:
    return shlex.join(command)


def _build_generate_command(*, representative_dir: Path, flow: str | None, preset: str | None) -> list[str]:
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "generate_representative_genes.py"),
        "--out",
        str(representative_dir),
    ]
    if flow:
        command.extend(["--flow", flow])
    if preset:
        command.extend(["--preset", preset])
    return command


def _build_mesh_study_command(
    *,
    representative_dir: Path,
    study_dir: Path,
    case_set: str,
    profiles: list[str],
    flow: str | None,
    preset: str | None,
    solver_cmd: str,
    ranks: int | None,
) -> list[str]:
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "run_su2_mesh_study.py"),
        "--out",
        str(study_dir),
        "--solver-cmd",
        solver_cmd,
    ]
    if flow:
        command.extend(["--flow", flow])
    if preset:
        command.extend(["--preset", preset])
    if ranks is not None:
        command.extend(["--ranks", str(ranks)])
    for profile in profiles:
        command.extend(["--profile", profile])

    if case_set == "anchor3":
        for case_name in ANCHOR_CASES:
            command.extend(["--gene", str(representative_dir / "genes" / f"{case_name}.json")])
    elif case_set == "representative7":
        command.extend(
            [
                "--batch-summary",
                str(representative_dir / "batch_summary.json"),
                "--representative-study",
                "--representative-limit",
                "7",
            ]
        )
    else:
        raise ValueError(f"Unsupported case_set: {case_set}")

    return command


def _build_manifest_markdown(manifest: dict) -> str:
    lines = [
        "# SU2 Overnight Batch",
        "",
        f"- GeneratedAt: {manifest['GeneratedAt']}",
        f"- Purpose: {manifest['Purpose']}",
        f"- WhyThisMatters: {manifest['WhyThisMatters']}",
        f"- CaseSet: {manifest['CaseSet']}",
        f"- Profiles: {', '.join(manifest['Profiles'])}",
        f"- SolverCommand: {manifest['SolverCommand']}",
        f"- Ranks: {manifest['Ranks']}",
        f"- RepresentativeDir: {manifest['RepresentativeDir']}",
        f"- StudyDir: {manifest['StudyDir']}",
        f"- DryRun: {manifest['DryRun']}",
        "",
        "## Planned Commands",
        "",
        "```bash",
        manifest["GenerateCommand"],
        manifest["MeshStudyCommand"],
        "```",
        "",
        "## Output Expectations",
        "",
        "- `representative_cases/`: generated archetype genes and proxy summaries",
        "- `mesh_study/mesh_study_summary.json`: next-day SU2 result summary",
        "- `logs/*.log`: full stdout/stderr of each step",
        "",
    ]
    return "\n".join(lines) + "\n"


def _run_command(command: list[str], *, log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as handle:
        process = subprocess.run(
            command,
            cwd=project_root,
            text=True,
            stdout=handle,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return int(process.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="啟動 unattended SU2 驗證 batch")
    parser.add_argument("--out", help="batch 輸出根目錄；未指定時會自動帶時間戳")
    parser.add_argument("--flow", help="流體條件 JSON 檔案路徑")
    parser.add_argument("--preset", choices=["none", "hpa"], help="限制 preset（預設讀 analysis_config）")
    parser.add_argument("--case-set", choices=["anchor3", "representative7"], default=DEFAULT_CASE_SET, help="要跑的案例集合")
    parser.add_argument("--profile", action="append", choices=["coarse", "baseline", "fine", "finer"], default=[], help="mesh study profiles，可重複提供")
    parser.add_argument("--solver-cmd", default="SU2_CFD", help="SU2 solver 指令，預設 SU2_CFD")
    parser.add_argument("--ranks", type=int, help="MPI ranks；未指定時預設 1~4 間的安全值")
    parser.add_argument("--dry-run", action="store_true", help="只寫 manifest 與 planned commands，不實際執行")
    args = parser.parse_args()

    defaults = load_analysis_config(os.path.join(project_root, "config", "analysis_config.json"))
    preset = args.preset or defaults["preset"]
    profiles = args.profile or list(DEFAULT_PROFILES)
    ranks = args.ranks if args.ranks is not None else _default_ranks()

    if args.out:
        root = Path(args.out)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        root = Path("output") / f"su2_overnight_batch_{timestamp}"

    representative_dir = root / "representative_cases"
    study_dir = root / "mesh_study"
    logs_dir = root / "logs"
    root.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    generate_command = _build_generate_command(
        representative_dir=representative_dir,
        flow=args.flow,
        preset=preset,
    )
    mesh_command = _build_mesh_study_command(
        representative_dir=representative_dir,
        study_dir=study_dir,
        case_set=args.case_set,
        profiles=profiles,
        flow=args.flow,
        preset=preset,
        solver_cmd=args.solver_cmd,
        ranks=ranks,
    )

    manifest = {
        "GeneratedAt": datetime.now().isoformat(),
        "Purpose": "Build a family-level SU2 evidence set, not a one-off pretty case.",
        "WhyThisMatters": (
            "The overnight batch checks whether the current SU2 workflow remains stable across "
            "multiple fairing archetypes, so we can judge family-level credibility before "
            "touching proxy calibration or running bigger GA searches."
        ),
        "CaseSet": args.case_set,
        "Profiles": profiles,
        "SolverCommand": args.solver_cmd,
        "Ranks": ranks,
        "RepresentativeDir": str(representative_dir),
        "StudyDir": str(study_dir),
        "DryRun": bool(args.dry_run),
        "GenerateCommand": _stringify_command(generate_command),
        "MeshStudyCommand": _stringify_command(mesh_command),
        "LogFiles": {
            "generate_representative": str(logs_dir / "generate_representative.log"),
            "mesh_study": str(logs_dir / "mesh_study.log"),
        },
    }

    manifest_json = root / "overnight_manifest.json"
    manifest_md = root / "overnight_manifest.md"
    manifest_json.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest_md.write_text(_build_manifest_markdown(manifest), encoding="utf-8")

    if args.dry_run:
        print("SU2 overnight batch dry-run 已準備完成")
        print(f"overnight_manifest.json: {manifest_json}")
        print(f"representative_cases/: {representative_dir}")
        print(f"mesh_study/: {study_dir}")
        return 0

    generate_rc = _run_command(generate_command, log_path=logs_dir / "generate_representative.log")
    if generate_rc != 0:
        print("代表案例產生失敗，請查看 log。", file=sys.stderr)
        print(f"log: {logs_dir / 'generate_representative.log'}", file=sys.stderr)
        return generate_rc

    mesh_rc = _run_command(mesh_command, log_path=logs_dir / "mesh_study.log")
    if mesh_rc != 0:
        print("SU2 mesh study 執行失敗，請查看 log。", file=sys.stderr)
        print(f"log: {logs_dir / 'mesh_study.log'}", file=sys.stderr)
        return mesh_rc

    print("SU2 overnight batch 執行完成")
    print(f"overnight_manifest.json: {manifest_json}")
    print(f"mesh_study_summary.json: {study_dir / 'mesh_study_summary.json'}")
    print(f"mesh_study_summary.md: {study_dir / 'mesh_study_summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
