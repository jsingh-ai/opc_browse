from __future__ import annotations

from copy import deepcopy


def split_opc_path(path: str | None) -> list[str]:
    if not path:
        return []
    return [segment.strip() for segment in path.split("/") if segment.strip()]


def _new_node(name: str, path: str) -> dict:
    return {"name": name, "path": path, "children": [], "tags": []}


def build_tag_tree(tag_rows: list[dict]) -> dict:
    root = _new_node("root", "")

    for row in tag_rows:
        path_segments = split_opc_path(row.get("opc_path"))
        if not path_segments:
            root["tags"].append(deepcopy(row))
            continue

        current = root
        current_path_parts: list[str] = []
        for segment in path_segments[:-1]:
            current_path_parts.append(segment)
            next_path = "/".join(current_path_parts)
            child = next(
                (candidate for candidate in current["children"] if candidate["name"] == segment),
                None,
            )
            if child is None:
                child = _new_node(segment, next_path)
                current["children"].append(child)
                current["children"].sort(key=lambda item: item["name"].lower())
            current = child
        current["tags"].append(deepcopy(row))
        current["tags"].sort(
            key=lambda item: (
                item.get("display_name") or "",
                item.get("browse_name") or "",
                item.get("opc_path") or "",
            )
        )

    return root
