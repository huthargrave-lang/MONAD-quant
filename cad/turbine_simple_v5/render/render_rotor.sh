#!/usr/bin/env bash
# Render out/slides/v5_rotor_render.png from out/v5_rotor_PRINT.stl with three.js in headless Chromium (needs node, npm, playwright).
# View: 3/4 front, az 32, el 14, roll 40 deg, 10 deg FOV; transparent background, cropped to the part.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; V5="$(dirname "$HERE")"; PY="${PY:-python3}"
WORK="$(mktemp -d)"; trap 'kill ${SRV:-0} 2>/dev/null || true; rm -rf "$WORK"' EXIT
cp "$HERE/render_rotor.html" "$HERE/shot.js" "$WORK/"
(cd "$WORK" && npm init -y >/dev/null && npm install three@0.169.0 --no-audit --no-fund >/dev/null)
"$PY" "$HERE/recenter_rotor.py" "$V5/out/v5_rotor_PRINT.stl" "$WORK/rotor.stl"
PORT=$((20000 + RANDOM % 20000)); (cd "$WORK" && python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1) & SRV=$!; sleep 1
(cd "$WORK" && node shot.js "http://127.0.0.1:$PORT/render_rotor.html?w=2600&h=2600&fov=10&az=32&el=14&roll=40&color=%237d8da3&env=0.4" "$WORK/full.png" 2600 2600)
"$PY" -c "
from PIL import Image; im = Image.open('$WORK/full.png').convert('RGBA'); bb = im.getchannel('A').point(lambda a: 255 if a > 8 else 0).getbbox(); p = 30
im.crop((bb[0] - p, bb[1] - p, bb[2] + p, bb[3] + p)).save('$V5/out/slides/v5_rotor_render.png'); print('written out/slides/v5_rotor_render.png')"
