# PSD → XCF Template Conversion Strategy

**Task:** td-250f2a  
**Status:** Research complete

## Decision: One-Time Batch Convert to XCF with Manual Verification

### Why Not Runtime PSD Loading?
1. **Performance**: XCF loads as memory dump (instant); PSD requires parsing on every load
2. **Reliability**: PSD import may silently degrade layers during batch runs
3. **Text layers**: PSD import rasterizes most text layers — we need editable text for automation
4. **Consistency**: XCF ensures identical results every run

---

## Import Fidelity Matrix

| PSD Feature | GIMP 3 Import | Risk | Mitigation |
|---|---|---|---|
| Layer names | ✅ Exact match | None | Verify against constants.py |
| Nested groups | ✅ Preserved | None | |
| Visibility states | ✅ Preserved | None | |
| Standard blend modes | ✅ Works | Low | Verify Multiply, Screen, Overlay |
| Non-standard blend modes | ⚠️ Approximate | Medium | Visual comparison per template |
| Opacity values | ✅ Preserved | None | |
| Text layers | ❌ Usually rasterized | **Critical** | Must recreate as native GIMP text |
| Smart Objects | ❌ Rasterized | High | Use placeholder layers + runtime load |
| Layer effects (drop shadow) | ⚠️ Rasterized/lost | High | Re-apply using GIMP effects |
| Layer masks | ✅ Generally preserved | Low | Verify complex masks |
| Clipping masks | ⚠️ Become groups | Medium | Update code to target groups |
| Adjustment layers | ⚠️ Partial | Medium | May need manual recreation |
| Vector shapes | ⚠️ Rasterized | Low | Acceptable for card templates |

---

## Conversion Workflow

### Phase 1: Automated Batch Convert

```python
#!/usr/bin/env python3
"""
Batch convert PSD templates to XCF.
Run inside GIMP: gimp-console-3.0 -i --batch-interpreter python-fu-eval \
  -b "exec(open('convert_templates.py').read())" -b "pdb.gimp_quit(0)"
"""
import os
import gi
gi.require_version('Gimp', '3.0')
from gi.repository import Gimp, Gio

def convert_all(psd_dir, xcf_dir):
    os.makedirs(xcf_dir, exist_ok=True)
    
    for filename in sorted(os.listdir(psd_dir)):
        if not filename.lower().endswith('.psd'):
            continue
        
        psd_path = os.path.join(psd_dir, filename)
        xcf_name = filename.rsplit('.', 1)[0] + '.xcf'
        xcf_path = os.path.join(xcf_dir, xcf_name)
        
        # Load PSD
        gfile = Gio.File.new_for_path(psd_path)
        image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, gfile)
        
        # Save as XCF
        out_gfile = Gio.File.new_for_path(xcf_path)
        Gimp.file_save(
            Gimp.RunMode.NONINTERACTIVE,
            image,
            image.list_layers()[0],
            out_gfile
        )
        
        print(f"Converted: {filename} -> {xcf_name}")
        image.delete()

convert_all(
    "/path/to/mtg-photoshop-automation/templates",
    "/path/to/mtg-gimp-automation/templates"
)
```

### Phase 2: Layer Structure Verification

```python
"""
Dump all layer names from XCF files for verification.
Compares against expected layer names from constants.py.
"""
def dump_layer_tree(image_or_group, indent=0):
    """Recursively print layer tree."""
    if hasattr(image_or_group, 'get_layers'):
        layers = image_or_group.get_layers()
    elif hasattr(image_or_group, 'get_children'):
        layers = image_or_group.get_children()
    else:
        return
    
    for layer in layers:
        layer_type = "GROUP" if layer.is_group() else (
            "TEXT" if layer.is_text_layer() else "LAYER"
        )
        visible = "V" if layer.get_visible() else "H"
        prefix = "  " * indent
        print(f"{prefix}[{layer_type}][{visible}] {layer.get_name()}")
        
        if layer.is_group():
            dump_layer_tree(layer, indent + 1)
```

### Phase 3: Manual Text Layer Recreation

For each XCF template:

1. **Open in GIMP 3 GUI**
2. **Identify rasterized text layers** — they'll appear as normal layers, not text layers
3. **For each text layer that the automation needs to edit:**
   - Note the layer's position, size, and visual appearance
   - Delete the rasterized layer
   - Create a new Text Layer with the correct name, font, and size
   - Position it in the same location
   - Set the correct font (Beleren, PlantinMTPro, etc.)
4. **Save the XCF**

**Layers that MUST be editable text:**
- `"Card Name"` — Beleren2016-Bold-Asterisk
- `"Mana Cost"` — NDPMTG
- `"Type Line"` — PlantinMTPro-Bold
- `"Rules Text"` — PlantinMTPro-Regular (with Pango markup)
- `"Rules Text Noncreature"` — Same as Rules Text
- `"Power / Toughness"` — Beleren2016-Bold-Asterisk
- `"Expansion Symbol"` — Keyrune font (or loaded as image layer)
- Any other text layers referenced in `text_layers.jsx`

**Layers that DON'T need to be editable:**
- Frame color layers (just visibility toggled)
- Art frame (just position/size)
- Background layers
- Decorative elements

### Phase 4: Automated Verification Script

```python
"""
Verify all required layers exist in each XCF template.
Cross-reference with constants.py layer names.
"""
from constants import LAYERS  # The converted constants module

def verify_template(xcf_path, required_layers):
    gfile = Gio.File.new_for_path(xcf_path)
    image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, gfile)
    
    found = set()
    missing = []
    
    def collect_names(group):
        for layer in (group.get_layers() if hasattr(group, 'get_layers') 
                      else group.get_children()):
            found.add(layer.get_name())
            if layer.is_group():
                collect_names(layer)
    
    collect_names(image)
    
    for name in required_layers:
        if name not in found:
            missing.append(name)
    
    image.delete()
    
    if missing:
        print(f"FAIL: {xcf_path}")
        for name in missing:
            print(f"  Missing: {name}")
    else:
        print(f"OK: {xcf_path}")
    
    return len(missing) == 0
```

---

## Template File Inventory

Based on `templates.jsx` (25+ template classes), the PSD files to convert include:

| Template Class | Expected PSD File | Priority |
|---|---|---|
| NormalTemplate | `normal.psd` | P0 |
| NormalClassicTemplate | `normalClassic.psd` | P1 |
| NormalExtendedTemplate | `normalExtended.psd` | P1 |
| NormalFullArtTemplate | `normalFullArt.psd` | P1 |
| TransformFrontTemplate | `transformFront.psd` | P1 |
| TransformBackTemplate | `transformBack.psd` | P1 |
| MDFCFrontTemplate | `mdfcFront.psd` | P1 |
| MDFCBackTemplate | `mdfcBack.psd` | P1 |
| PlaneswalkerTemplate | `planeswalker.psd` | P1 |
| SagaTemplate | `saga.psd` | P1 |
| AdventureTemplate | `adventure.psd` | P1 |
| LevelerTemplate | `leveler.psd` | P1 |
| MutateTemplate | `mutate.psd` | P1 |
| BasicLandTemplate | `basicLand.psd` | P1 |
| TokenTemplate | `token.psd` | P2 |
| PlanarTemplate | `planar.psd` | P2 |

*Exact filenames need verification against the actual templates/ directory.*

---

## Timeline Estimate

| Phase | Effort | Notes |
|---|---|---|
| Batch convert script | 1 hour | Write once, run once |
| Verification script | 1 hour | Automated layer checking |
| Manual text layer recreation | 2-4 hours per template × ~16 templates | 32-64 hours total — **largest effort** |
| Automated verification | 30 minutes | Run after each template fix |

**Total: ~40-70 hours** for template conversion. This is the single largest work item in the project and should be parallelized — multiple templates can be fixed simultaneously.

---

## Risk Mitigations

1. **Start with `normal.psd`** — the most-used template, validates the entire workflow
2. **Keep original PSDs** — never modify, always regenerate XCF from PSD if needed
3. **Version control XCFs** — track changes to templates
4. **Automated regression** — render same card in Photoshop and GIMP, pixel-diff the output
5. **Font installation** — ensure all required fonts are installed in GIMP before conversion
