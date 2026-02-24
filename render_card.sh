#!/usr/bin/env bash
set -euo pipefail

# render_card.sh — Fetch card data from Scryfall, download art, and render via GIMP.
#
# Usage:
#   ./render_card.sh "Lightning Bolt"
#   ./render_card.sh "Lightning Bolt" --set 2XM
#   ./render_card.sh "Lightning Bolt" --artist "Christopher Moeller"
#   ./render_card.sh "Lightning Bolt" --set 2XM --artist "Christopher Moeller"
#   ./render_card.sh "Lightning Bolt" --skip-render   # fetch only, no GIMP

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
ART_DIR="${PROJECT_DIR}/art"
OUT_DIR="${PROJECT_DIR}/out"

CARD_NAME=""
CARD_SET=""
ARTIST=""
SKIP_RENDER=false

# ── Parse arguments ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --set|-s)
            CARD_SET="$2"
            shift 2
            ;;
        --artist|-a)
            ARTIST="$2"
            shift 2
            ;;
        --skip-render)
            SKIP_RENDER=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 <card-name> [--set <SET>] [--artist <ARTIST>] [--skip-render]"
            echo
            echo "  <card-name>       Card name to search on Scryfall (required)"
            echo "  --set, -s         Set code (e.g. 2XM, ELD, MH2)"
            echo "  --artist, -a      Override artist name in filename"
            echo "  --skip-render     Fetch card data and art only, skip GIMP render"
            echo
            echo "Examples:"
            echo "  $0 \"Lightning Bolt\""
            echo "  $0 \"Lightning Bolt\" --set 2XM"
            echo "  $0 \"Counterspell\" --artist \"Zack Stella\" --set MH2"
            exit 0
            ;;
        -*)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
        *)
            CARD_NAME="$1"
            shift
            ;;
    esac
done

if [[ -z "$CARD_NAME" ]]; then
    echo "Error: Card name is required." >&2
    echo "Usage: $0 <card-name> [--set <SET>] [--artist <ARTIST>] [--skip-render]" >&2
    exit 1
fi

# ── Step 1: Query Scryfall API ───────────────────────────────────────────────
echo "==> Fetching card data from Scryfall..."

ENCODED_NAME=$(python3 -c "from urllib.parse import quote; print(quote('${CARD_NAME}'))")
SCRYFALL_URL="https://api.scryfall.com/cards/named?fuzzy=${ENCODED_NAME}"

if [[ -n "$CARD_SET" ]]; then
    ENCODED_SET=$(python3 -c "from urllib.parse import quote; print(quote('${CARD_SET}'))")
    SCRYFALL_URL="${SCRYFALL_URL}&set=${ENCODED_SET}"
fi

CARD_JSON=$(curl -sS -H "User-Agent: MTG-GIMP-Automation/1.0" "$SCRYFALL_URL")

# Check for Scryfall error
if echo "$CARD_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('object')=='card' else 1)" 2>/dev/null; then
    echo "    Card found!"
else
    echo "Error: Scryfall could not find '${CARD_NAME}'." >&2
    echo "$CARD_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print('  Detail:', d.get('details','unknown'))" 2>/dev/null || true
    exit 1
fi

# Extract card details into shell variables (shlex.quote ensures safe eval)
eval $(echo "$CARD_JSON" | python3 -c "
import sys, json, shlex
d = json.load(sys.stdin)
name = d.get('name', '')
artist = d.get('artist', 'Unknown')
uris = d.get('image_uris') or {}
if not uris and 'card_faces' in d:
    uris = d['card_faces'][0].get('image_uris') or {}
url = uris.get('large') or uris.get('normal') or uris.get('small') or ''
layout = d.get('layout', 'normal')
set_name = d.get('set_name', '')
set_code = d.get('set', '')
mana = d.get('mana_cost', '')
type_line = d.get('type_line', '')
print(f'REAL_NAME={shlex.quote(name)}')
print(f'REAL_ARTIST={shlex.quote(artist)}')
print(f'IMAGE_URL={shlex.quote(url)}')
print(f'CARD_LAYOUT={shlex.quote(layout)}')
print(f'SET_NAME={shlex.quote(set_name)}')
print(f'SET_CODE={shlex.quote(set_code)}')
print(f'MANA_COST={shlex.quote(mana)}')
print(f'TYPE_LINE={shlex.quote(type_line)}')
")

echo "    Name:     ${REAL_NAME}"
echo "    Artist:   ${REAL_ARTIST}"
echo "    Set:      ${SET_NAME} (${SET_CODE})"
echo "    Type:     ${TYPE_LINE}"
echo "    Mana:     ${MANA_COST}"
echo "    Layout:   ${CARD_LAYOUT}"

# Use provided artist or fall back to Scryfall artist
if [[ -n "$ARTIST" ]]; then
    FILE_ARTIST="$ARTIST"
else
    FILE_ARTIST="$REAL_ARTIST"
fi

# ── Step 2: Download card art ────────────────────────────────────────────────
ART_FILE="${ART_DIR}/${REAL_NAME} (${FILE_ARTIST}).jpg"

mkdir -p "$ART_DIR" "$OUT_DIR"

if [[ -f "$ART_FILE" ]]; then
    echo "==> Art file already exists: $(basename "$ART_FILE")"
    echo "    Skipping download. Delete it to re-download."
else
    if [[ -z "$IMAGE_URL" ]]; then
        echo "Error: No image URL available from Scryfall." >&2
        exit 1
    fi
    echo "==> Downloading card art..."
    curl -sS -o "$ART_FILE" "$IMAGE_URL"
    echo "    Saved: $(basename "$ART_FILE")"
fi

# Save the JSON for reference
echo "$CARD_JSON" | python3 -m json.tool > "${PROJECT_DIR}/card.json"
echo "==> Card JSON saved to card.json"

# ── Step 3: Render via GIMP ──────────────────────────────────────────────────
if [[ "$SKIP_RENDER" == true ]]; then
    echo "==> Skipping render (--skip-render)."
    echo "    Art file: ${ART_FILE}"
    echo "    Run GIMP manually or re-run without --skip-render."
    exit 0
fi

echo "==> Launching GIMP render..."
gimp -id --batch-interpreter=python-fu-eval -b "
import sys
sys.path.insert(0, '${PROJECT_DIR}')
from src.render_target import run
run(target_file='${ART_FILE}', project_path='${PROJECT_DIR}')
" --quit

echo "==> Done! Output: ${OUT_DIR}/${REAL_NAME}.png"