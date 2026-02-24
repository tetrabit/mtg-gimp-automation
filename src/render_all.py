"""Batch render all cards from the art/ folder."""

import glob
import importlib
import os


def run(project_path=None):
    """Render all card art files in the art/ directory."""
    if project_path is None:
        project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if __package__:
        from .render import render
    else:
        render = importlib.import_module("src.render").render

    art_dir = os.path.join(project_path, "art")
    patterns = ["*.jpg", "*.jpeg", "*.png", "*.tif"]
    files = []
    for pattern in patterns:
        files.extend(glob.glob(os.path.join(art_dir, pattern)))

    for file_path in sorted(files):
        try:
            render(file_path, project_path)
        except Exception as error:
            if "Exiting" in str(error):
                break
            print(f"Error rendering {file_path}: {error}")
            raise


if __name__ == "__main__":
    run()
