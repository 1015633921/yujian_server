from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BINARY_SUFFIXES = {
    ".gif", ".ico", ".jpeg", ".jpg", ".pdf", ".png", ".ttf", ".webp", ".woff", ".woff2", ".xlsx", ".zip"
}
PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\b(?:ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{20,}\b"),
    "Tencent access key": re.compile(r"\bAKID[A-Za-z0-9]{16,}\b"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "WeChat API v3 key": re.compile(r"(?i)(?:WECHAT_PAY_API_V3_KEY|WX_PAY_API_V3_KEY)\s*=\s*[A-Za-z0-9]{32}"),
}


def candidate_paths() -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / item.decode("utf-8") for item in completed.stdout.split(b"\0") if item]


def main() -> int:
    findings: list[str] = []
    for path in candidate_paths():
        if not path.is_file() or path.suffix.lower() in BINARY_SUFFIXES:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(ROOT)
        for label, pattern in PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{relative}: possible {label}")
    if findings:
        print("secret scan failed")
        for finding in findings:
            print(finding)
        return 1
    print("secret scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
