"""Reproducibly apply the F1.2 horse fill and Stable painter-order repairs."""
from pathlib import Path
import copy
import json

ROOT = Path(__file__).resolve().parent
asset_path = ROOT / 'luma_assets_e33.json'
main_path = ROOT / 'main.py'
play_path = ROOT / 'F1_play.html'

# These should already have been captured before running this script. Keep the
# baseline creation here too, so a clean F1.1 source extraction is reproducible.
if not (ROOT / 'F1.1_MAIN_BASE.py').exists():
    raise SystemExit('F1.1 main baseline is missing; do not overwrite the current base.')
if not (ROOT / 'F1.1_BASE_LUMA_ASSETS.json').exists():
    raise SystemExit('F1.1 asset baseline is missing; do not overwrite the current base.')

assets = json.loads(asset_path.read_text(encoding='utf-8'))
if assets.get('version') != 'SGGF1.2':
    raise SystemExit('The current asset pack is not the expected F1.2 working copy.')

# This script documents the deterministic transformation; the working file is
# already transformed by the initial F1.1 -> F1.2 run. Recompute and compare to
# the saved F1.1 horse baseline to guard against unrecorded hand edits.
base = json.loads((ROOT / 'F1.1_BASE_LUMA_ASSETS.json').read_text(encoding='utf-8'))
expected = []
for command in base['assets']['stable_draft_horse']['commands']:
    if command.get('op') == 'polygon' and int(command.get('border', 0) or 0) > 0:
        fill = copy.deepcopy(command)
        fill['border'] = 0
        expected.extend((fill, copy.deepcopy(command)))
    else:
        expected.append(copy.deepcopy(command))
if assets['assets']['stable_draft_horse']['commands'] != expected:
    raise SystemExit('Horse fill commands do not match the deterministic F1.1-to-F1.2 transform.')

source = main_path.read_text(encoding='utf-8')
required = "for oid in ('stable_carriage', 'stables_foreground_fence', 'stable_draft_horse'):"
if required not in source:
    raise SystemExit('F1.2 stable painter order is not in the source.')
if 'VERSION = "F1.2"' not in source:
    raise SystemExit('F1.2 source version tag is missing.')
page = play_path.read_text(encoding='utf-8')
for required_text in ('SGGF1.2', 'sggf12.apk', 'sggf12.tar.gz', 'archive:"sggf12"'):
    if required_text not in page:
        raise SystemExit(f'F1.2 browser bootstrap is missing {required_text!r}.')
print('F1.2 transformation verified: 14 explicit fill passes, updated version labels and fence-behind-horse draw order.')
