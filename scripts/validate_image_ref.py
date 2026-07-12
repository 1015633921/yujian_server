from __future__ import annotations

import argparse
import re


IMMUTABLE_IMAGE = re.compile(r"^[a-zA-Z0-9._:/-]+@sha256:[0-9a-f]{64}$")


def main() -> int:
    parser = argparse.ArgumentParser(description="Reject mutable container image references")
    parser.add_argument("image")
    args = parser.parse_args()
    if not IMMUTABLE_IMAGE.fullmatch(args.image):
        print("image reference must use repository@sha256:<64 hex digest>")
        return 1
    print("immutable image reference accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
