"""Render a single target card."""

import os
import sys
import importlib


def run(target_file=None, project_path=None):
    """Render a specific card art file."""
    if project_path is None:
        project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if __package__:
        from .config import FILE_TARGET as file_target_default
        from .render import render
    else:
        file_target_default = importlib.import_module("src.config").FILE_TARGET
        render = importlib.import_module("src.render").render

    if target_file is None:
        target_file = os.path.join(project_path, "art", file_target_default)

    if not os.path.exists(target_file):
        print(f"Target file not found: {target_file}")
        sys.exit(1)

    render(target_file, project_path)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run(target_file=sys.argv[1])
    else:
        run()
