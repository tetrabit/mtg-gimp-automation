# Agentic Workflow — MTG Card Generation + Visual Verification

## Overview

This document describes the workflow for using an AI agent (Claude/Sisyphus) to iteratively generate MTG proxy card images and verify them visually. Because GIMP runs headlessly and the card rendering system is complex, visual verification is an essential part of the development loop.

---

## The Core Constraint: 1MB Image Limit

AI vision models cannot analyze images larger than ~1MB. This is a hard limit of the tool infrastructure.

**Why this matters**: The GIMP render pipeline produces 3288×4488px images. A lossless PNG at this size is ~25MB — completely unviewable by the agent. Without image analysis, the agent cannot verify whether a card rendered correctly, spot layout bugs, or check text positioning.

**Solution**: Output in JPEG format with a size cap.

```python
# src/config.py
OUTPUT_FORMAT = "jpeg"
OUTPUT_MAX_SIZE_KB = 1000  # Hard limit — agent must be able to view the file
```

The export logic steps JPEG quality from 95 down in increments of 5 until the file fits under 1MB. This produces ~950–999KB files that retain enough visual fidelity for the agent to evaluate card layout and typography.

---

## Workflow Loop

```
┌─────────────────────────────────────────────────────────────┐
│  1. Identify rendering issue (user report or prior failure) │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Hypothesize root cause                                  │
│     Read relevant src/ files                                │
│     Trace execution path through pipeline                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Make targeted code change                               │
│     Edit one variable / one function at a time              │
│     Run lsp_diagnostics on changed files                    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Render a test card (timeout 300s)                       │
│     gimp -id --batch-interpreter=python-fu-eval -b '...'   │
│     Watch for Python exceptions in stdout                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  5. View rendered image                                     │
│     look_at(file_path="out/CardName.jpg", goal="...")       │
│     Evaluate layout, text, symbols against target criteria  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    ┌──────┴──────┐
                    │             │
                  Pass          Fail
                    │             │
                    ▼             ▼
             Mark task       Back to step 2
             complete        (new hypothesis)
```

---

## Step 4: Render Command

The canonical render command for Lightning Bolt (test card):

```bash
timeout 300 gimp -id --batch-interpreter=python-fu-eval -b '
import sys, traceback
sys.path.insert(0, "/home/nullvoid/projects/mtg-gimp-automation")
try:
    from src.render import render_card
    render_card(
        "/home/nullvoid/projects/mtg-gimp-automation/art/Lightning Bolt (Christopher Moeller).jpg",
        "/home/nullvoid/projects/mtg-gimp-automation"
    )
except Exception as e:
    print("ERROR:", e)
    traceback.print_exc()
import gi
Gimp = getattr(__import__("gi.repository", fromlist=["Gimp"]), "Gimp")
pdb = Gimp.get_pdb()
proc = pdb.lookup_procedure("gimp-quit")
cfg = proc.create_config()
cfg.set_property("force", True)
proc.run(cfg)
' 2>&1 | tail -50
```

Critical flags:
- `-id` only — NOT `-idf`. The `-f` flag skips font loading, causing immediate crashes.
- `timeout 300` — GIMP batch mode can hang indefinitely on certain errors.
- `| tail -50` — GIMP prints startup messages; card errors appear at the end.

---

## Step 5: Visual Verification

Use `look_at()` on the output JPEG to evaluate the rendered card:

```python
look_at(
    file_path="out/Lightning Bolt.jpg",
    goal="Evaluate card layout. Check: (1) card name visible and correctly positioned, "
         "(2) mana cost symbols in top-right, (3) art fills the art box without overflow, "
         "(4) type line present with correct text, (5) oracle text legible and word-wrapped "
         "within the text box, (6) expansion symbol in bottom-right of type bar, "
         "(7) P/T box absent (non-creature card), (8) no text overlaps or clipping. "
         "Rate each element 1-10 and identify any failures."
)
```

### Verification Checklist

For any rendered card, check each element:

| Element | Expected |
|---|---|
| Card Name | Top-left text bar, Beleren font, correct name |
| Mana Cost | Top-right, NDPMTG mana symbols, correct cost |
| Art | Fills art box, no overflow into text box |
| Type Line | Below art, PlantinMTPro Bold, correct type string |
| Expansion Symbol | Right end of type bar, correct set glyph, rarity color stroke |
| Oracle Text | Text box, word-wrapped, PlantinMTPro Regular, full text visible |
| Flavor Text | Italic, separated from oracle text (if applicable) |
| P/T Box | Present only for creature cards, correct numbers |
| Frame | Correct color(s) for card's color identity |
| No Artifacts | No layer bleed, no misaligned layers, no clipped text |

---

## Interpreting Render Errors

### Python Exception in GIMP stdout

```
ERROR: 'NoneType' object has no attribute 'get_width'
Traceback (most recent call last):
  File ".../src/templates.py", line 312, in set_expansion_symbol
    w = sym_layer.get_width()
```

→ `get_layer()` returned `None`. Layer name mismatch. Check `constants.py` and verify against actual XCF layer names.

### GIMP Hangs (timeout fires)

→ Usually an infinite loop in a retry/quality-step loop, or a GIMP internal deadlock. Add print statements to isolate last successful step.

### Blank Output / Zero-Byte File

→ JPEG export crashed before writing. Check for exceptions before the `export_jpeg()` call.

### GIMP Exits with "No fonts found"

→ `-f` flag was used. Always use `-id`, never `-idf`.

### Pango Markup Error

```
Error parsing Pango markup: unexpected end of markup
```

→ Unescaped `&`, `<`, or `>` in oracle text. All card text must pass through `escape_pango()` before being placed inside `<span>` tags.

---

## Iterative Calibration Pattern

For layout/positioning issues, the pattern is:

1. **Read the XCF template dimensions** — actual pixel positions of reference layers
2. **Identify which constant controls the element** — font size, layer offset, or text box width
3. **Change one constant** — no multi-variable changes in a single iteration
4. **Re-render and view**
5. **Binary search toward target** — if too big, halve the delta; if correct direction, continue

Example: Calibrating rules text font size:

```
Initial: FONT_SIZE_RULES_TEXT = 80.0
View:    Text too small, much whitespace below
Change:  FONT_SIZE_RULES_TEXT = 120.0
View:    Text overflows box
Change:  FONT_SIZE_RULES_TEXT = 100.0
View:    ✓ Good fit, all text visible, slight margin
Accept
```

---

## Multi-Card Verification

After fixing a rendering issue, verify on at least two different card types:

1. **Lightning Bolt** — Simple instant, no creature, `{R}` mana cost, short oracle text, flavor text
2. **Counterspell** — Instant, `{U}{U}` mana cost, longer oracle text, no flavor text

Different cards exercise different code paths (mana symbol count, text length, P/T box visibility, etc.). A fix that works for one card may break another.

---

## Agent-Specific Constraints

### Image size must stay under 1MB

Always verify `out/*.jpg` file size before calling `look_at()`:

```bash
ls -lh out/
```

If the file exceeds 1MB, the `look_at()` call will fail or return a degraded result. Lower `OUTPUT_MAX_SIZE_KB` in `config.py` if needed (900 is a safe floor).

### GIMP stdout is noisy

GIMP prints version info, font scanning progress, and plugin messages before any Python output. Always pipe through `| tail -N` (N=50 is usually enough) or search for `ERROR:` and `Traceback` in the output.

### One change at a time

Never change multiple layout constants in the same render iteration. With multiple changes, it's impossible to attribute the visual effect to a specific variable when reviewing the image.

### Keep diagnostic renders small

When debugging, use a card with short oracle text (Lightning Bolt, Giant Growth) rather than long ones (Omniscience). Shorter text means positioning errors are more visually obvious and less masked by wrapping behavior.

---

## Output Files

```
out/
├── Lightning Bolt.jpg     # Primary test card (~950KB)
├── Counterspell.jpg       # Secondary test card (~980KB)
└── ...                    # Other rendered cards (gitignored)
```

Output files are gitignored. Only source code and documentation are tracked.

---

## Acceptance Criteria

A rendering pass is accepted when `look_at()` evaluates:
- All card elements present (name, mana, art, type, rules, expansion symbol)
- Text readable and not clipped
- Frame correct color for card's identity
- No obvious visual artifacts
- Rating ≥ 7/10 for each element category

Cards rated below 7/10 on any element require a new iteration.
