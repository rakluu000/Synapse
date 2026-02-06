from __future__ import annotations

import argparse
import datetime as _dt
from pathlib import Path

from .common import (
    SynapseError,
    find_project_root,
    load_defaults,
    slugify,
    synapse_paths,
    utc_now_iso,
)
from .context_pack import build_context_pack
from .state import rebuild_index, update_state


def cmd_pack(args: argparse.Namespace) -> int:
    defaults = load_defaults()
    project_root = find_project_root(Path(args.project_dir))
    paths = synapse_paths(project_root)

    from .common import ensure_synapse_layout

    ensure_synapse_layout(paths)

    phase = (getattr(args, "phase", None) or "pack").strip()
    if not phase:
        raise SynapseError("pack requires a non-empty --phase")

    query = getattr(args, "query", None)
    query = str(query) if query is not None else ""

    slug = getattr(args, "slug", None)
    slug = str(slug).strip() if isinstance(slug, str) else ""
    if not slug:
        if query.strip():
            slug = slugify(query)
        else:
            slug = _dt.datetime.now().strftime(f"{phase}-%Y%m%d-%H%M%S")

    rg_queries = list(getattr(args, "rg_query", []) or [])
    include_files_raw = list(getattr(args, "include_file", []) or [])
    include_files: list[Path] = []
    for p in include_files_raw:
        pp = Path(p)
        include_files.append(pp if pp.is_absolute() else (project_root / pp).resolve())

    context_pack = build_context_pack(
        paths=paths,
        defaults=defaults,
        slug=slug,
        phase=phase,
        query=query,
        rg_queries=rg_queries if rg_queries else None,
        include_files=include_files if include_files else None,
    )

    rebuild_index(paths)
    update_state(
        paths,
        last={
            "command": "pack",
            "slug": slug,
            "phase": phase,
            "query": query,
            "context_pack": str(context_pack),
            "at": utc_now_iso(),
        },
    )

    print(f"slug: {slug}")
    print(f"phase: {phase}")
    if query.strip():
        print(f"query: {query.strip()}")
    print(f"context_pack: {context_pack}")
    return 0

