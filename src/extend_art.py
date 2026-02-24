# pyright: reportMissingImports=false
# pyright: reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false
import gi
gi.require_version('Gimp', '3.0')
import gi.repository as gir
import glob
import os

Gimp = getattr(gir, "Gimp")
Gio = getattr(gir, "Gio")
Gegl = getattr(gir, "Gegl")
GObject = getattr(gir, "GObject")


def _run_procedure(name, args):
    return Gimp.get_pdb().run_procedure(name, args)


def _apply_heal_selection(drawable):
    pdb = Gimp.get_pdb()
    candidates = (
        "gimp-drawable-filter-apply",
        "gimp-drawable-merge-filter",
        "gimp-drawable-apply-operation",
    )

    for procedure_name in candidates:
        try:
            _run_procedure(
                procedure_name,
                [
                    GObject.Value(Gimp.Drawable, drawable),
                    GObject.Value(str, "gegl:heal-selection"),
                ],
            )
            return
        except Exception:
            continue

    try:
        procedure = pdb.lookup_procedure("gimp-drawable-filter-new")
        config = procedure.create_config()
        config.set_property("drawable", drawable)
        config.set_property("operation-name", "gegl:heal-selection")
        config.set_property("name", "heal-selection")
        result = procedure.run(config)
        if len(result) > 1:
            drawable_filter = result[1]
            commit = pdb.lookup_procedure("gimp-drawable-filter-commit")
            commit_config = commit.create_config()
            commit_config.set_property("filter", drawable_filter)
            commit.run(commit_config)
    except Exception:
        pass


def content_fill_empty_area(image, drawable):
    if drawable is None:
        drawable = image.get_active_drawable()
    if drawable is None:
        return

    if hasattr(drawable, "discard_text_information"):
        drawable.discard_text_information()

    image_value = GObject.Value(Gimp.Image, image)

    _run_procedure("gimp-selection-none", [image_value])
    _run_procedure(
        "gimp-image-select-item",
        [
            image_value,
            GObject.Value(Gimp.ChannelOps, Gimp.ChannelOps.REPLACE),
            GObject.Value(Gimp.Item, drawable),
        ],
    )
    _run_procedure("gimp-selection-invert", [image_value])
    _run_procedure(
        "gimp-selection-grow",
        [
            image_value,
            GObject.Value(GObject.TYPE_INT, 10),
        ],
    )
    _run_procedure(
        "gimp-selection-feather",
        [
            image_value,
            GObject.Value(GObject.TYPE_DOUBLE, 4.0),
        ],
    )

    _apply_heal_selection(drawable)
    _run_procedure("gimp-selection-none", [image_value])


def extend_art(file_path):
    image = Gimp.file_load(
        Gimp.RunMode.NONINTERACTIVE,
        Gio.File.new_for_path(file_path),
    )

    image.flatten()

    old_width = image.get_width()
    old_height = image.get_height()

    new_width = int(round(old_width * 1.10))
    new_height = int(round(old_height * 1.05))

    offset_x = int((new_width - old_width) / 2)
    offset_y = int(new_height - old_height)

    image.resize(new_width, new_height, offset_x, offset_y)
    drawable = image.flatten()

    content_fill_empty_area(image, drawable)

    output_file = Gio.File.new_for_path(file_path)
    Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, drawable, output_file)
    image.delete()


def extend_all():
    project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    art_dir = os.path.join(project_path, "art")
    patterns = ("*.jpg", "*.jpeg", "*.png", "*.tif", "*.tiff", "*.webp")

    files = []
    for pattern in patterns:
        files.extend(glob.glob(os.path.join(art_dir, pattern)))

    for file_path in sorted(files):
        extend_art(file_path)


if __name__ == "__main__":
    extend_all()
