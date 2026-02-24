# pyright: reportMissingImports=false
# pyright: reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false
import os

import gi
gi.require_version('Gimp', '3.0')
import gi.repository as gir

from src.helpers import find_layer_by_name, frame_layer, paste_file_into_new_layer, save_and_close

Gimp = getattr(gir, "Gimp")  # pyright: ignore[reportAny]
Gio = getattr(gir, "Gio")  # pyright: ignore[reportAny]


def borderify(file_path):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_path = os.path.join(project_root, "templates", "MPCcrop.xcf")
    image = Gimp.file_load(  # pyright: ignore[reportAny]
        Gimp.RunMode.NONINTERACTIVE,  # pyright: ignore[reportAny]
        Gio.File.new_for_path(template_path),  # pyright: ignore[reportAny]
    )

    art_layer = paste_file_into_new_layer(image, file_path)
    reference_layer = find_layer_by_name(image, "Card Size")
    if reference_layer is None:
        image.delete()  # pyright: ignore[reportAny]
        raise RuntimeError('Layer "Card Size" not found in templates/MPCcrop.xcf')

    frame_layer(image, art_layer, reference_layer)
    image.flatten()  # pyright: ignore[reportAny]

    border_dir = os.path.join(project_root, "out", "border")
    os.makedirs(border_dir, exist_ok=True)
    file_name = os.path.splitext(os.path.basename(file_path))[0]
    save_and_close(image, os.path.join("border", file_name), project_root)


def borderify_all():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(project_root, "out")
    if not os.path.isdir(out_dir):
        return

    for entry in sorted(os.listdir(out_dir)):
        file_path = os.path.join(out_dir, entry)
        if os.path.isfile(file_path) and entry.lower().endswith(".png"):
            borderify(file_path)
