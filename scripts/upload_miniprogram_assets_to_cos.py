"""Backward-compatible entrypoint for the unified CDN asset manager."""

from __future__ import annotations

import sys

from miniprogram_assets import main


def translate_legacy_arguments(arguments: list[str]) -> list[str]:
    if arguments and arguments[0] in {"prepare", "publish", "verify"}:
        return arguments
    environment = "test"
    translated = list(arguments)
    if "--env" in translated:
        index = translated.index("--env")
        try:
            environment = translated[index + 1]
        except IndexError as exc:
            raise SystemExit("--env requires test or prod") from exc
        del translated[index:index + 2]
    return ["publish", environment, *translated]


if __name__ == "__main__":
    sys.argv[1:] = translate_legacy_arguments(sys.argv[1:])
    raise SystemExit(main())
