"""Run one P04 opportunity assessment from a JSON file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.scoring.p04_engine import (
    DecisionPackage,
    JsonlQuarantineStore,
    QuarantineRecord,
    QuarantineType,
    process_opportunity,
)


def _read_input(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _write_output(path: Path, rendered: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(rendered + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate one ACCESS ALGERIA P04 opportunity record."
    )
    parser.add_argument("input", type=Path, help="P04 input JSON file")
    parser.add_argument(
        "--output",
        type=Path,
        help="new JSON decision-package file; omit to print to stdout",
    )
    parser.add_argument(
        "--quarantine",
        type=Path,
        help="append quarantine records to this JSONL file",
    )
    args = parser.parse_args(argv)

    store = JsonlQuarantineStore(args.quarantine) if args.quarantine else None
    try:
        try:
            payload = _read_input(args.input)
        except json.JSONDecodeError as exc:
            quarantine_rec = QuarantineRecord(
                record_type=QuarantineType.STRUCTURAL_VALIDATION_FAILURE,
                reason_codes=["P04_INVALID_JSON"],
                details=[f"Invalid JSON at line {exc.lineno}, column {exc.colno}."],
            )
            if store is not None:
                store.append(quarantine_rec)
            result: DecisionPackage | QuarantineRecord = quarantine_rec
        else:
            result = process_opportunity(payload, quarantine_store=store)
    except (OSError, UnicodeError) as exc:
        print(f"P04 could not read input or write quarantine: {exc}", file=sys.stderr)
        return 1

    result_type = (
        "quarantine_record"
        if isinstance(result, QuarantineRecord)
        else "decision_package"
    )
    rendered = json.dumps(
        {
            "result_type": result_type,
            "result": result.model_dump(mode="json"),
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    try:
        if args.output:
            _write_output(args.output, rendered)
        else:
            print(rendered)
    except OSError as exc:
        print(f"P04 could not write the output: {exc}", file=sys.stderr)
        return 1

    return 2 if isinstance(result, QuarantineRecord) else 0


if __name__ == "__main__":
    raise SystemExit(main())