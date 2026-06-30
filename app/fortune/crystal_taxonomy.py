from __future__ import annotations

from .config import load_config


def crystal_taxonomy() -> dict[str, dict]:
    return load_config("crystal_taxonomy.json")


def taxonomy_for(code: str) -> dict:
    data = crystal_taxonomy()
    item = dict(data.get(code, {}) or {})
    parent_code = item.pop("extends", "")
    if parent_code:
        parent = taxonomy_for(parent_code)
        return {**parent, **item}
    return item


def crystal_elements(code: str, crystal: dict) -> set[str]:
    taxonomy = taxonomy_for(code)
    return {
        crystal["element"],
        *crystal.get("secondary_elements", []),
        *taxonomy.get("elements", []),
    }
