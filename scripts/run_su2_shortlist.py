"""
Run prepared SU2 shortlist cases and summarize the results.

This command assumes the shortlist package already exists and that each case
contains a valid `.su2` mesh matching the marker names in `su2_case.cfg`.
"""

from __future__ import annotations

import argparse
import os
import sys

from _bootstrap import ensure_src_path


project_root = os.fspath(ensure_src_path())

from analysis import SU2ExecutionError, run_shortlist_su2_cases


def main() -> int:
    parser = argparse.ArgumentParser(description="執行已準備好的 SU2 shortlist case")
    parser.add_argument("--shortlist-dir", required=True, help="SU2 shortlist 目錄")
    parser.add_argument("--case", action="append", default=[], help="只執行指定 case，可重複提供")
    parser.add_argument("--solver-cmd", default="SU2_CFD", help="SU2 solver 指令，預設 SU2_CFD")
    parser.add_argument("--ranks", type=int, help="MPI ranks；未指定時用 serial SU2_CFD")
    parser.add_argument("--timeout", type=int, help="每個 case 的 timeout 秒數")
    parser.add_argument("--continue-on-error", action="store_true", help="某個 case 失敗時繼續跑其他 case")
    parser.add_argument("--dry-run", action="store_true", help="只檢查命令與 case 結構，不實際執行 SU2")
    args = parser.parse_args()

    try:
        summary = run_shortlist_su2_cases(
            args.shortlist_dir,
            solver_command=args.solver_cmd,
            mpi_ranks=args.ranks,
            timeout_seconds=args.timeout,
            selected_cases=args.case,
            continue_on_error=args.continue_on_error,
            dry_run=args.dry_run,
        )
    except SU2ExecutionError as exc:
        print(f"錯誤: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"執行 SU2 shortlist 失敗: {exc}", file=sys.stderr)
        return 1

    print("SU2 shortlist 執行完成")
    print(f"TotalCases: {summary['TotalCases']}")
    print(f"SuccessfulCases: {summary['SuccessfulCases']}")
    print(f"FailedCases: {summary['FailedCases']}")
    print(f"su2_run_summary.json: {summary['SummaryFiles']['json']}")
    print(f"su2_run_summary.md: {summary['SummaryFiles']['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
