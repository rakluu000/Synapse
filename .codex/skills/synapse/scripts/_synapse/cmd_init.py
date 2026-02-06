from __future__ import annotations

import argparse
from pathlib import Path

from .agents_md import ensure_agents_md, ensure_gitignore
from .common import find_project_root, synapse_paths, utc_now_iso
from .state import rebuild_index, update_state


def cmd_init(args: argparse.Namespace) -> int:
    project_root = find_project_root(Path(args.project_dir))
    paths = synapse_paths(project_root)

    from .common import ensure_synapse_layout

    ensure_synapse_layout(paths)

    ensure_gitignore(project_root)
    ensure_agents_md(project_root)

    rebuild_index(paths)
    update_state(paths, last={"command": "init", "at": utc_now_iso()})

    print(f"project_root: {project_root}")
    print(f"synapse_dir: {paths.synapse_dir}")
    print(f"state: {paths.state_json}")
    print(f"index: {paths.index_json}")
    return 0

