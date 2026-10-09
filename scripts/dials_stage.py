#!/usr/bin/env python3
"""Run one explicitly chosen DIALS command in a new, audited directory."""
import argparse
import glob
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

PROGRAMS = {"import", "find_spots", "index", "refine_bravais_settings", "reindex",
            "refine", "integrate", "combine_experiments", "split_experiments",
            "symmetry", "scale", "two_theta_refine", "export", "report"}


def fingerprint(path):
    path = Path(path).resolve(strict=True)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def expand_arguments(arguments):
    result = []
    for arg in arguments:
        if "=" not in arg and glob.has_magic(arg):
            matches = sorted(glob.glob(arg))
            if not matches:
                raise ValueError(f"Input pattern matched no files: {arg}")
            result.extend(str(Path(item).resolve()) for item in matches)
        elif "=" not in arg and Path(arg).exists():
            result.append(str(Path(arg).resolve()))
        else:
            result.append(arg)
    return result


def run_stage(command, out, inputs=(), expected=(), timeout=None, dry_run=False):
    out = Path(out).resolve()
    input_records = [fingerprint(path) for path in inputs]
    # Expected outputs are relative to the fresh stage, never source paths.
    for name in expected:
        target = (out / name).resolve()
        if target == out or out not in target.parents:
            raise ValueError(f"Expected output escapes stage: {name}")
    out.mkdir(parents=True, exist_ok=False)
    record = {"command": command, "cwd": str(out), "inputs": input_records,
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "python": sys.version, "dry_run": dry_run}
    (out / "command.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    status = {"state": "dry_run" if dry_run else "running"}
    failure = None
    if not dry_run:
        try:
            with (out / "console.txt").open("w", encoding="utf-8") as log:
                result = subprocess.run(command, cwd=out, stdout=log,
                                        stderr=subprocess.STDOUT, timeout=timeout,
                                        check=False, shell=False)
            status["exit_code"] = result.returncode
            if result.returncode:
                failure = f"Program exited with {result.returncode}"
            else:
                missing = [name for name in expected
                           if not (out / name).is_file() or (out / name).stat().st_size == 0]
                if missing:
                    failure = f"Missing or empty expected outputs: {missing}"
                else:
                    status["outputs"] = [fingerprint(out / name) for name in expected]
        except Exception as exc:
            failure = f"{type(exc).__name__}: {exc}"
        status["state"] = "failed" if failure else "completed"
    status["finished_utc"] = datetime.now(timezone.utc).isoformat()
    if failure:
        status["error"] = failure
    (out / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    if failure:
        raise RuntimeError(f"{failure}; retained logs in {out}")
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--program", required=True, choices=sorted(PROGRAMS))
    parser.add_argument("--dials-bin", type=Path, help="Directory containing DIALS launchers")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--input", action="append", default=[], help="Explicit provenance file; repeat")
    parser.add_argument("--expect", action="append", default=[], help="Relative output filename; repeat")
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    name = "dials." + args.program + (".exe" if os.name == "nt" else "")
    executable = str(args.dials_bin / name) if args.dials_bin else shutil.which(name)
    if not executable or not Path(executable).is_file():
        parser.error(f"Cannot locate {name}; activate DIALS or specify --dials-bin")
    arguments = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
    command = [str(Path(executable).resolve()), *expand_arguments(arguments)]
    status = run_stage(command, args.out, args.input, args.expect, args.timeout, args.dry_run)
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
