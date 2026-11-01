"""Apply the narrowly scoped Castle Path transition polish to the F1.2 baseline."""
from pathlib import Path
import copy
import json

HERE = Path(__file__).resolve().parent
BASE_MAIN = HERE / 'F1.2_BASE_MAIN.py'
BASE_ASSETS = HERE / 'F1.2_BASE_LUMA_ASSETS.json'
MAIN = HERE / 'main.py'
ASSETS = HERE / 'luma_assets_e33.json'
PLAY = HERE / 'F1_play.html'

source = BASE_MAIN.read_text(encoding='utf-8')
old_version = 'VERSION = "F1.2"  # Independent Stables carriage and draft horse assets.'
new_version = 'VERSION = "F1.3"  # Castle Path transition marker and safe return placement.'
assert source.count(old_version) == 1
source = source.replace(old_version, new_version, 1)

# The E5.6 crossing rule remains untouched. Only its visual affordance is added
# in the existing transition-arrow painter below.
start = source.index('    def _draw_edge_arrows(self,surface,g):')
end = source.index('    def _c1_text(self,surface,s,x,y,color,font,width):', start)
new_method = '''    def _draw_edge_arrows(self,surface,g):
        # Every edge link gets its own marker, including Gold District's TWO right-side exits.
        for conn,center in g.edge_markers():
            direction=conn.edge
            if (g.current_area_id == 'castle_path'
                    and conn.connection_id == 'castle_path_top_castle_exterior'):
                # The Castle Path marker is visual guidance only. The actual
                # transition remains the invisible E5.6 threshold crossing.
                approach = E56StateMachine.CASTLE_APPROACH
                forward = E56StateMachine.CASTLE_FORWARD
                lateral = E56StateMachine.CASTLE_LATERAL
                x = round(approach[0] + forward[0] * 40.0)
                y = round(approach[1] + forward[1] * 40.0)
                local_points = [(14,0),(-4,-13),(-4,-5),(-12,-5),
                                (-12,5),(-4,5),(-4,13)]
                points = [
                    (round(x + forward[0]*along + lateral[0]*across),
                     round(y + forward[1]*along + lateral[1]*across))
                    for along,across in local_points
                ]
                # Keep the caption beside the arrow, toward the upper-right,
                # clear of Spiffy and styled like the other transition labels.
                label_x = round(x + lateral[0]*56 + forward[0]*4)
                label_y = round(y + lateral[1]*56 + forward[1]*4)
                label_rect = pygame.Rect(label_x-95,label_y-10,190,19)
            elif g.current_area_id == 'gold_district' and direction == 'top':
                # E5.1: this route now enters Castle Path through an actual
                # gated stone passage at the back of the district. Its arrow
                # must be attached to the GATE, not to the empty sky at Y=52.
                x=int(max(60,min(GAME_WIDTH-60,center)))
                y=318
                points=[(x,y-14),(x-13,y+4),(x-5,y+4),
                        (x-5,y+12),(x+5,y+12),(x+5,y+4),(x+13,y+4)]
                label_rect=pygame.Rect(x-105,y+18,210,19)
            elif direction in ('top','bottom'):
                x=int(max(60,min(GAME_WIDTH-60,center)))
                y=52 if direction=='top' else GAME_HEIGHT-24
                points=([(x,y-14),(x-13,y+4),(x-5,y+4),(x-5,y+12),(x+5,y+12),(x+5,y+4),(x+13,y+4)]
                        if direction=='top' else
                        [(x,y+13),(x-13,y-4),(x-5,y-4),(x-5,y-12),(x+5,y-12),(x+5,y-4),(x+13,y-4)])
                text_y=y+14 if direction=='top' else y-60
                label_rect=pygame.Rect(x-105,text_y,210,19)
            else:
                x=20 if direction=='left' else GAME_WIDTH-20
                y=int(max(105,min(GAME_HEIGHT-55,center)))
                points=([(x-14,y),(x+4,y-13),(x+4,y-5),(x+12,y-5),(x+12,y+5),(x+4,y+5),(x+4,y+13)]
                        if direction=='left' else
                        [(x+14,y),(x-4,y-13),(x-4,y-5),(x-12,y-5),(x-12,y+5),(x-4,y+5),(x-4,y+13)])
                label_rect=pygame.Rect(37 if direction=='left' else GAME_WIDTH-217,y-29,180,19)
            pygame.draw.polygon(surface,(30,28,37),points)
            pygame.draw.polygon(surface,(250,209,104),points,3)
            name=g.areas[conn.to_area_id].display_name
            caption=self.game_small_font.render(name[:21],True,(251,232,172))
            panel=caption.get_rect(center=label_rect.center).inflate(10,3)
            pygame.draw.rect(surface,(28,27,32),panel,border_radius=3)
            surface.blit(caption,caption.get_rect(center=label_rect.center))

'''
source = source[:start] + new_method + source[end:]

old_status = "self._set_status('SGGF1.2: independent carriage and draft horse; Part One remains intact.')"
new_status = "self._set_status('SGGF1.3: Castle Path transition marker and safe return; F1.2 Stables and Part One retained.')"
assert source.count(old_status) == 1
source = source.replace(old_status, new_status, 1)
old_header = 'label = "SPIFFY\'S GIFT  |  F1.2  |  " + (\'BROWSER\' if BROWSER else \'DESKTOP\')'
new_header = 'label = "SPIFFY\'S GIFT  |  F1.3  |  " + (\'BROWSER\' if BROWSER else \'DESKTOP\')'
assert source.count(old_header) == 1
source = source.replace(old_header, new_header, 1)
MAIN.write_text(source, encoding='utf-8')

base = json.loads(BASE_ASSETS.read_text(encoding='utf-8'))
new_doc = copy.deepcopy(base)
new_doc['version'] = 'SGGF1.3'

# Remove the complete three-pass annotation stroke: dark under-stroke, gold
# stroke and highlight. These three commands are one visual line, not scenery.
background = new_doc['assets']['c1_bg_castle_path']['commands']
marker = [c for c in background
          if c.get('op') == 'line'
          and c.get('points') == [[748,435],[834,307]]]
assert len(marker) == 3, f'Expected the exact three-pass yellow guide line, found {len(marker)}'
new_doc['assets']['c1_bg_castle_path']['commands'] = [
    c for c in background
    if not (c.get('op') == 'line' and c.get('points') == [[748,435],[834,307]])
]

reverse = next(c for c in new_doc['world']['connections']
               if c['connection_id'] == 'castle_exterior_bottom_castle_path')
reverse['arrival_x'] = 834
reverse['arrival_y'] = 400
new_doc['notes'] = (new_doc.get('notes', '').rstrip() +
    '\nSGGF1.3: removed the temporary Castle Path threshold guide stroke, added a visible Castle Exterior direction arrow beyond the unchanged invisible crossing threshold, and moved the Castle Exterior return landing safely onto the Castle Path approach. All other F1.2 assets, areas, gameplay, and transition logic are retained.')
ASSETS.write_text(json.dumps(new_doc, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')

page = PLAY.read_text(encoding='utf-8')
for old, new in (
    ('SGGF1.2', 'SGGF1.3'),
    ('sggf12', 'sggf13'),
):
    assert old in page
    page = page.replace(old, new)
PLAY.write_text(page, encoding='utf-8')

print('Applied F1.3: full temporary line removed; invisible E5.6 crossing code untouched; Castle Exterior arrow/label added; return landing moved to (834, 400); all other art/world/gameplay retained.')
