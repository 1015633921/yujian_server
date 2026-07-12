from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def command_version(command: list[str]) -> str:
    completed = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    match = re.search(r"(\d+\.\d+\.\d+)", completed.stdout or completed.stderr)
    if not match:
        raise RuntimeError(f"cannot parse version from {' '.join(command)}")
    return match.group(1)


def main() -> int:
    package = json.loads((ROOT / "miniprogram" / "package.json").read_text(encoding="utf-8"))
    expected = {
        "python": (ROOT / ".python-version").read_text(encoding="utf-8").strip(),
        "node": (ROOT / ".nvmrc").read_text(encoding="utf-8").strip(),
        "npm": package["engines"]["npm"],
    }
    actual = {
        "python": ".".join(str(part) for part in sys.version_info[:3]),
        "node": command_version(["node", "--version"]),
        "npm": command_version(["npm", "--version"]),
    }
    mismatches = [name for name in expected if expected[name] != actual[name]]
    if mismatches:
        for name in mismatches:
            print(f"{name}: expected {expected[name]}, got {actual[name]}", file=sys.stderr)
        return 1
    print("toolchain versions match pinned release versions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
