from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path


def read_record(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=True, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def promote(state_dir: Path, record: dict[str, object]) -> None:
    current = state_dir / "current.json"
    previous = state_dir / "previous.json"
    existing = read_record(current)
    if existing:
        atomic_write(previous, existing)
    atomic_write(current, record)


def rollback(state_dir: Path) -> None:
    current = read_record(state_dir / "current.json")
    previous = read_record(state_dir / "previous.json")
    if not previous:
        raise RuntimeError("no previous release recorded")
    atomic_write(state_dir / "current.json", previous)
    if current:
        atomic_write(state_dir / "previous.json", current)


def main() -> int:
    parser = argparse.ArgumentParser(description="Maintain atomic, non-secret release state")
    parser.add_argument("command", choices=("promote", "rollback", "show"))
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--which", choices=("current", "previous"), default="current")
    parser.add_argument("--field", choices=("release", "slot", "port", "project", "image"))
    parser.add_argument("--release")
    parser.add_argument("--slot", choices=("blue", "green"))
    parser.add_argument("--port", type=int)
    parser.add_argument("--project")
    parser.add_argument("--image")
    args = parser.parse_args()
    if args.command == "promote":
        values = {key: getattr(args, key) for key in ("release", "slot", "port", "project", "image")}
        if any(value in (None, "") for value in values.values()):
            parser.error("promote requires release, slot, port, project and image")
        promote(args.state_dir, values)
    elif args.command == "rollback":
        rollback(args.state_dir)
    else:
        record = read_record(args.state_dir / f"{args.which}.json")
        if not record:
            return 2
        print(record.get(args.field, "") if args.field else json.dumps(record, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
