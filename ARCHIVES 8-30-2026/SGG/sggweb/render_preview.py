"""PIL preview renderer matching LumaDrawEngine's stroke-only border semantics."""
from pathlib import Path
import json
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
D = json.loads((ROOT / 'luma_assets_e33.json').read_text(encoding='utf-8'))
ASSETS = D['assets']
S = 3


def draw_recipe(im, recipe, x, y, w=None, h=None):
    asset = ASSETS[recipe]
    w = w or asset['width']
    h = h or asset['height']
    sx, sy = w / asset['width'], h / asset['height']
    dr = ImageDraw.Draw(im)
    for c in asset['commands']:
        col = tuple(c.get('color', (255, 255, 255)))
        op = c['op']
        border = int(round(float(c.get('border', 0)) * S * (abs(sx) + abs(sy)) / 2))
        if op in ('rect', 'ellipse'):
            rx, ry, rw, rh = c['rect']
            box = ((x + rx * sx) * S, (y + ry * sy) * S,
                   (x + (rx + rw) * sx) * S, (y + (ry + rh) * sy) * S)
            if op == 'rect':
                if border:
                    dr.rectangle(box, outline=col, width=max(1, border))
                else:
                    dr.rectangle(box, fill=col)
            else:
                if border:
                    dr.ellipse(box, outline=col, width=max(1, border))
                else:
                    dr.ellipse(box, fill=col)
        elif op == 'polygon':
            pts = [((x + px * sx) * S, (y + py * sy) * S) for px, py in c['points']]
            if border:
                # Critical: the real LumaDrawEngine treats border as stroke-only.
                # F1.2 therefore places a border=0 fill command before each outline.
                dr.line(pts + [pts[0]], fill=col, width=max(1, border), joint='curve')
            else:
                dr.polygon(pts, fill=col)
        elif op == 'line':
            pts = [((x + px * sx) * S, (y + py * sy) * S) for px, py in c['points']]
            dr.line(pts, fill=col, width=max(1, int(round(c.get('width', 1) * S * (sx + sy) / 2))), joint='curve')
        elif op == 'circle':
            cx, cy = c['center']
            r = c['radius'] * S * (sx + sy) / 2
            box = ((x + cx * sx) * S - r, (y + cy * sy) * S - r,
                   (x + cx * sx) * S + r, (y + cy * sy) * S + r)
            if border:
                dr.ellipse(box, outline=col, width=max(1, border))
            else:
                dr.ellipse(box, fill=col)


# Full Stable yard, matching the live static-prop painter order: carriage, fence, horse.
scene = Image.new('RGBA', (1280 * S, 640 * S), (42, 43, 43, 255))
draw_recipe(scene, 'c1_bg_stables', 0, 0, 1280, 640)
objects = {o['object_id']: o for o in D['world']['objects']}
for object_id in ('stable_carriage', 'stables_foreground_fence', 'stable_draft_horse'):
    obj = objects[object_id]
    draw_recipe(scene, obj['kind'], obj['x'], obj['y'], obj['width'], obj['height'])
# The driver/vendor remains above the static props, as in LumaInterface.
vendor = next(a for a in D['world']['areas'] if a['area_id'] == 'stables')['vendors'][0]
role = D.get('render_roles', {}).get('vendor', 'vendor')
w, h = int(vendor.get('width', 56)), int(vendor.get('height', 77))
draw_recipe(scene, role, vendor['x'] - w / 2, vendor['y'] - h / 2, w, h)
scene.resize((1280, 640), Image.Resampling.LANCZOS).save(ROOT / 'F1.2_STABLES_PREVIEW.png')

# Transparent isolated horse plus light-backed inspection copy.
horse = Image.new('RGBA', (200 * S, 200 * S), (0, 0, 0, 0))
draw_recipe(horse, 'stable_draft_horse', 0, 0, 200, 200)
horse.resize((600, 600), Image.Resampling.LANCZOS).save(ROOT / 'F1.2_HORSE_ASSET_PREVIEW.png')
light = Image.new('RGBA', (600, 600), (239, 234, 220, 255))
light.alpha_composite(horse.resize((600, 600), Image.Resampling.LANCZOS))
light.convert('RGB').save(ROOT / 'F1.2_HORSE_ASSET_PREVIEW_LIGHT.png')
print('Rendered F1.2 previews with stroke-only border behavior and corrected stable depth order.')
