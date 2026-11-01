from pathlib import Path
import copy, json, math, re, shutil
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
MAIN = HERE / 'main.py'
ASSETS = HERE / 'luma_assets_e33.json'
BASE_MAIN = HERE / 'F1.4_BASE_MAIN.py'
BASE_ASSETS = HERE / 'F1.4_BASE_LUMA_ASSETS.json'
BASE_PLAY = HERE / 'F1.4_BASE_F1_play.html'

# Keep a pristine F1.4 copy beside the F1.5 build for reproducible scope checks.
if not BASE_MAIN.exists(): shutil.copy2(MAIN, BASE_MAIN)
if not BASE_ASSETS.exists(): shutil.copy2(ASSETS, BASE_ASSETS)
if not BASE_PLAY.exists(): shutil.copy2(HERE / 'F1_play.html', BASE_PLAY)

# ---------------------------------------------------------------------------
# 1. Update the main program with the F1.5 vault interaction and settings.
# ---------------------------------------------------------------------------
ASSETS.write_bytes(BASE_ASSETS.read_bytes())
src = BASE_MAIN.read_text(encoding='utf-8')
assert 'VERSION = "F1.4"' in src and 'SGGF1.4:' in src

src = src.replace(
    'VERSION = "F1.4"  # Castle Exterior architecture matched to the F1.3 Castle Path.',
    'VERSION = "F1.5"  # Castle Hall vault door, interactions and configurable platter hitbox.'
)
src = src.replace(
    '    "hidden_chest_hitbox_scale": 2.0,\n    "bubble_duration_seconds": 3.0,',
    '    "hidden_chest_hitbox_scale": 2.0,\n    "bubble_duration_seconds": 3.0,\n    "special_hard_hitbox": 3.0,'
)
src = src.replace(
    '    result["bubble_duration_seconds"] = round(min(10.0, max(1.0, bubble)), 1)\n    for field, fallback in',
    '    result["bubble_duration_seconds"] = round(min(10.0, max(1.0, bubble)), 1)\n'
    '    try:\n        special_hitbox = float(result.get("special_hard_hitbox", 3.0))\n'
    '    except (ValueError, TypeError, OverflowError):\n        special_hitbox = 3.0\n'
    '    if not math.isfinite(special_hitbox): special_hitbox = 3.0\n'
    '    result["special_hard_hitbox"] = round(min(5.0, max(1.0, special_hitbox)), 1)\n'
    '    for field, fallback in'
)

# Preserve the old C1.4 platter check as the default method. F1.5 overrides it.
old_clip = '''            # Hidden seam is passable ONLY while holding a platter and pressing toward it.
            if (g.current_area_id=='castle_hall' and not g.c1_dead and
                g.carried_object_id and (o:=g.object_by_id(g.carried_object_id)) and o.kind=='plate' and
                970<g.player_x<1070 and 210<g.player_y<405 and dx>0):
                conn=g.activate_connection('clip',source_object_id='vault_wall_seam')
                if conn:g.c1_vault_entered=True;self._area_enter(conn)
'''
new_clip = '''            # The hidden seam is delegated so later releases can tune the
            # platter target without changing the underlying connection.
            if self._plate_clip_trigger(g, dx):
                conn=g.activate_connection('clip',source_object_id='vault_wall_seam')
                if conn:g.c1_vault_entered=True;self._area_enter(conn)
'''
assert old_clip in src
src = src.replace(old_clip, new_clip, 1)
needle = '''    def _activate(self,obj):
        g=self.game
        if not g:return
'''
insert = '''    def _plate_clip_trigger(self, g, dx):
        """Original F1.4 platter/seam target, retained by default."""
        held = g.object_by_id(g.carried_object_id) if g and g.carried_object_id else None
        return bool(g and g.current_area_id == 'castle_hall' and not g.c1_dead
                    and held and held.kind == 'plate'
                    and 970 < g.player_x < 1070 and 210 < g.player_y < 405 and dx > 0)

    def _activate(self,obj):
        g=self.game
        if not g:return
'''
assert needle in src
src = src.replace(needle, insert, 1)

# Add locked_door to the F1 model hit-test domain (not to normal door walking).
needle = '''class F1GameModel(E56GameModel):
    """E5.7 world with durable Part One completion flags."""

    def c1_make_item(self, name, kind, *, price=0, area=None, stolen=False):
'''
replacement = '''class F1GameModel(E56GameModel):
    """E5.7 world with durable Part One completion flags and an interactable vault."""

    def hit_test(self, point):
        # The bank vault is point-and-E interactive, but is deliberately NOT a
        # walk-through door and receives no normal door transition.
        if point is not None and self.current_area_id == 'castle_hall':
            vault = self.object_by_id('vault_locked_door')
            if (vault is not None and vault.area_id == 'castle_hall'
                    and not vault.in_inventory and vault.rect().inflate(8, 8).collidepoint(point)):
                return vault
        return super().hit_test(point)

    def c1_make_item(self, name, kind, *, price=0, area=None, stolen=False):
'''
assert needle in src
src = src.replace(needle, replacement, 1)

# Add the five-control configuration, off-centre hitbox, and vault dialogs.
needle = '''class F1StateMachine(E57StateMachine):
    """F1.2 gameplay layer: F1.0 quest/finale retained; Stables props separated."""

    def _f1_upgrade_model(self):
'''
replacement = '''F15_SLIDER_TRACKS = (
    (445, 157, 390, 15),
    (445, 236, 390, 15),
    (445, 315, 390, 15),
    (445, 394, 390, 15),
    (445, 473, 390, 15),
)
F15_SLIDER_RANGES = ((1.0, 4.0), (5.0, 90.0), (1.0, 5.0), (1.0, 10.0), (1.0, 5.0))


class F1StateMachine(E57StateMachine):
    """F1.5 retains Part One while adding the bank-vault puzzle and hitbox tuning."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.special_hard_hitbox = float(self.config.get('special_hard_hitbox', 3.0))
        self.f15_vault_inventory_page = 0
        self._log('F1.5 CONFIG', f'special_hard_hitbox={self.special_hard_hitbox:.1f}')

    def _f15_plate_clip_rect(self):
        """An off-centre plate target tucked over the vault's right-hand seam.

        Setting 1 is generous, setting 5 is a precise little target. Its centre
        stays near the vault's right edge instead of drifting to the door centre.
        """
        value = max(1.0, min(5.0, float(getattr(self, 'special_hard_hitbox', 3.0))))
        width = round(92 - 16 * (value - 1))
        height = round(80 - 14 * (value - 1))
        return pygame.Rect(round(1046 - width / 2), round(333 - height / 2), width, height)

    def _plate_clip_trigger(self, g, dx):
        held = g.object_by_id(g.carried_object_id) if g and g.carried_object_id else None
        return bool(g and g.current_area_id == 'castle_hall' and not g.c1_dead
                    and held and held.kind == 'plate' and dx > 0
                    and self._f15_plate_clip_rect().collidepoint(round(g.player_x), round(g.player_y)))

    def _f15_set_special_hard_hitbox(self, value):
        value = round(max(1.0, min(5.0, float(value))), 1)
        if value == self.special_hard_hitbox:
            return
        error = self.persist_preference('special_hard_hitbox', value)
        if error:
            self._log('GAME CONFIG ERROR', f'Special Hard Hitbox: {error}')
            return
        self.special_hard_hitbox = value
        self._log('GAME CONFIG', f'special_hard_hitbox={value:.1f}; plate target={self._f15_plate_clip_rect()}')

    def _d1_adjust_slider(self, slot, value):
        if slot == 4:
            self._f15_set_special_hard_hitbox(value)
            return
        return super()._d1_adjust_slider(slot, value)

    def _d1_slider_pointer(self, pos, ui):
        point = ui.screen_to_game(pos)
        if point is None:
            return
        g = self.game
        slot = max(0, min(4, int(g.c13_slider_selected)))
        x, y, w, h = F15_SLIDER_TRACKS[slot]
        lo, hi = F15_SLIDER_RANGES[slot]
        t = max(0.0, min(1.0, (point[0] - x) / w))
        value = lo + t * (hi - lo)
        if slot == 1:
            value = round(value)
        else:
            value = round(value, 1)
        self._d1_adjust_slider(slot, value)

    def _f15_vault_main_dialogue(self):
        self._dialogue('THE BANK VAULT',
            'A magnificent steel vault door. A wheel of solid iron, six locking bolts, and a lever that practically dares you to try it.\\n\\nIt looks extremely expensive to argue with.',
            [{'text': 'Pick lock', 'action': 'f15_vault_pick_lock'},
             {'text': 'Force open', 'action': 'f15_vault_force_open'},
             {'text': 'Leave the vault alone', 'action': 'close'}])

    def _f15_vault_inventory_dialogue(self, page=0):
        g = self.game
        self.f15_vault_inventory_page = max(0, int(page))
        items = []
        for oid in g.inventory:
            obj = g.object_by_id(oid)
            if obj is not None and (obj.in_inventory or oid == g.carried_object_id) and obj.area_id != '__consumed__':
                items.append(obj)
        pages = max(1, (len(items) + 1) // 2)
        self.f15_vault_inventory_page = min(self.f15_vault_inventory_page, pages - 1)
        if not items:
            self._dialogue('THE BANK VAULT',
                'You rummage through your inventory. Nothing suitable presents itself. The vault is clearly judging your preparation.',
                [{'text': 'Back to the vault', 'action': 'f15_vault_main'}])
            return
        start = self.f15_vault_inventory_page * 2
        selected = items[start:start + 2]
        options = [{'text': f'Use {obj.name}', 'action': 'f15_vault_item:' + obj.object_id}
                   for obj in selected]
        if self.f15_vault_inventory_page < pages - 1:
            options.append({'text': 'More inventory items…', 'action': 'f15_vault_inventory_next'})
        if self.f15_vault_inventory_page > 0:
            options.append({'text': 'Previous inventory page', 'action': 'f15_vault_inventory_prev'})
        options.append({'text': 'Back to the vault', 'action': 'f15_vault_main'})
        self._dialogue('WHAT SHOULD I FORCE IT OPEN WITH?',
            f'Choose an item from your pack. Page {self.f15_vault_inventory_page + 1} of {pages}.', options)

    def _f15_vault_item_response(self, obj):
        kind = str(obj.kind).lower()
        name = str(obj.name)
        if kind == 'plate':
            line = 'Oddly the plate ALMOST squeezes in a gap. There is a tiny metallic click. The vault remains firmly, magnificently shut.'
        elif kind in ('key', 'skeleton_key') or 'key' in name.lower():
            line = 'You try the key. It enters the lock about as far as a polite suggestion enters a brick wall. Not even the Skeleton Key could manage this one.'
        elif kind == 'gold' or 'gold' in name.lower():
            line = 'You offer money to a bank vault. It is already full of money. The wheel does not move, but the vault seems mildly flattered.'
        elif kind == 'potion' or 'potion' in name.lower():
            line = 'The potion bubbles against the steel. The vault does not drink, does not blink, and does not budge.'
        elif kind == 'sammich' or 'sammich' in name.lower():
            line = 'You offer the vault an Egg McGuffin Sammich. It smells wonderful. The vault has no mouth and absolutely no intention of opening.'
        elif kind == 'tomato':
            line = 'The tomato splats against the steel with a satisfying plorp. The vault remains closed. The tomato is now a wall decoration.'
        elif kind == 'cabbage':
            line = 'You bash the vault with a cabbage. A leaf falls off. The vault is unmoved; the cabbage is emotionally bruised.'
        elif kind == 'bucket':
            line = 'You place the bucket over the vault wheel. It fits rather well. Unfortunately, the bucket is not a locksmith.'
        elif kind == 'soup':
            line = 'You pour soup over the locking mechanism. It smells better, but now the vault is both locked and sticky.'
        else:
            line = f'You try {name} against the wheel. It makes a brave little noise. The vault makes no noise at all, which is somehow worse.'
        self._dialogue('THE BANK VAULT', line,
            [{'text': 'Try another item', 'action': 'f15_vault_force_open'},
             {'text': 'Back to vault choices', 'action': 'f15_vault_main'},
             {'text': 'Give up for now', 'action': 'close'}])

    def _activate(self, obj):
        if obj is not None and obj.object_id == 'vault_locked_door':
            g = self.game
            if g is None:
                return
            if not g.close_to_object(obj):
                self._speech('Walk closer to the bank vault first.')
                return
            self._log('VAULT', 'Player examined the bank vault door; opening remains intentionally impossible.')
            self._f15_vault_main_dialogue()
            return
        return super()._activate(obj)

    def _dispatch_game(self, event, ui):
        # The comment editor owns its events even if the settings panel opened first.
        if getattr(self, 'e57_comment_open', False):
            return super()._dispatch_game(event, ui)
        g = self.game
        if g is not None and g.c13_game_config_open:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Keep the top-bar tools reachable while the settings panel is up.
                if ui.d11_tip_button().collidepoint(event.pos):
                    self._d11_open_tip(); return
                if ui.e41_export_button().collidepoint(event.pos):
                    self.e41_export(); return
                if ui.e57_comment_button().collidepoint(event.pos):
                    self._e57_open_comment(ui); return
                if ui.layout.menu_button.collidepoint(event.pos):
                    self._d1_menu(); return
                point = ui.screen_to_game(event.pos)
                if point is not None and pygame.Rect(E41_FOLDER_RECT).collidepoint(point):
                    self.e41_choose_folder(); return
                if point is not None and pygame.Rect(C13_GAME_CLOSE).collidepoint(point):
                    self._d1_menu(); return
                if point is not None:
                    for i, (x, y, w, h) in enumerate(F15_SLIDER_TRACKS):
                        if pygame.Rect(x-18, y-22, w+36, 55).collidepoint(point):
                            g.c13_slider_selected = i
                            g.c13_slider_dragging = True
                            self._d1_slider_pointer(event.pos, ui)
                            return
                return
            if event.type == pygame.MOUSEMOTION and g.c13_slider_dragging:
                self._d1_slider_pointer(event.pos, ui)
                return
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                g.c13_slider_dragging = False
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or c12_binding_matches(event, self.c1_keys['game_config']):
                    self._d1_menu()
                elif event.key in (pygame.K_UP, pygame.K_DOWN):
                    g.c13_slider_selected = (g.c13_slider_selected + (-1 if event.key == pygame.K_UP else 1)) % 5
                elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    slot = max(0, min(4, int(g.c13_slider_selected)))
                    values = (self.soup_speed_multiplier, self.soup_effect_seconds,
                              self.hidden_chest_hitbox_scale, self.bubble_duration_seconds,
                              self.special_hard_hitbox)
                    step = 1 if slot == 1 else 0.1
                    self._d1_adjust_slider(slot, values[slot] + (step if event.key == pygame.K_RIGHT else -step))
                return
            return
        return super()._dispatch_game(event, ui)

    def _f1_upgrade_model(self):
'''
assert needle in src
src = src.replace(needle, replacement, 1)

# Insert F1 vault action routing at the top of the current F1 _choose_dialogue.
needle = '''        action = options[index].get('action')

        if action == 'f1_driver_breakfast_info':
'''
replacement = '''        action = options[index].get('action')

        # Bank-vault dialogue is intentionally a closed loop: every choice is
        # entertaining, but no inventory item or puzzle answer opens the door.
        if action == 'f15_vault_pick_lock':
            g.c1_dialogue = None
            self._dialogue('THE BANK VAULT',
                "Are you kidding? Even the Skeleton Key ain't gonna pick this.",
                [{'text': 'Try forcing it open instead', 'action': 'f15_vault_force_open'},
                 {'text': 'Back to vault choices', 'action': 'f15_vault_main'}])
            return
        if action == 'f15_vault_force_open':
            g.c1_dialogue = None
            self._f15_vault_inventory_dialogue(0)
            return
        if action == 'f15_vault_inventory_next':
            g.c1_dialogue = None
            self._f15_vault_inventory_dialogue(self.f15_vault_inventory_page + 1)
            return
        if action == 'f15_vault_inventory_prev':
            g.c1_dialogue = None
            self._f15_vault_inventory_dialogue(self.f15_vault_inventory_page - 1)
            return
        if action == 'f15_vault_main':
            g.c1_dialogue = None
            self._f15_vault_main_dialogue()
            return
        if isinstance(action, str) and action.startswith('f15_vault_item:'):
            oid = action.split(':', 1)[1]
            obj = g.object_by_id(oid)
            g.c1_dialogue = None
            if obj is not None and oid in g.inventory:
                self._log('VAULT ITEM', f'Attempted to force vault with {obj.name} ({obj.kind}); vault remains closed.')
                self._f15_vault_item_response(obj)
            else:
                self._dialogue('THE BANK VAULT', 'That item is no longer in your pack. The vault waits, smugly.',
                    [{'text': 'Back to vault choices', 'action': 'f15_vault_main'}])
            return

        if action == 'f1_driver_breakfast_info':
'''
assert needle in src
src = src.replace(needle, replacement, 1)

src = src.replace(
    "self._set_status('SGGF1.4: Castle Exterior matches the Castle Path fortress; all F1.3 gameplay and transitions retained.')",
    "self._set_status('SGGF1.5: Castle Hall vault redesign, item dialogue and adjustable off-centre platter hitbox; F1.4 world retained.')"
)
# F1.4's class comment and version display were stale release labels.
src = src.replace('F1.2 gameplay layer: F1.0 quest/finale retained; Stables props separated.',
                  'F1.5 gameplay layer: F1.0 quest/finale retained; castle bank-vault puzzle added.')
src = src.replace('F1.2 display: stable prop layering; Kitty route and E5.7 comments retained.',
                  'F1.5 display: five persistent game sliders; Kitty route and E5.7 comments retained.')
src = src.replace('SPIFFY\'S GIFT  |  F1.4  |  ', 'SPIFFY\'S GIFT  |  F1.5  |  ')
# Update the help hint to make the three door meanings explicit.
src = src.replace(
    "'castle_hall': 'CASTLE: point + E to interact; walk through doors; platter + wall seam for vault.',",
    "'castle_hall': 'CASTLE HALL: LEFT=MAge room  |  MIDDLE=outside  |  RIGHT=bank vault (point + E); plate + off-centre seam to clip through.',"
)
src = src.replace(
    "'castle_hall': 'TREASURE ROOM: a platter and a suspicious wall seam might prove useful.',",
    "'castle_hall': 'CASTLE HALL: left door to Mage Room; middle door outside; right door is the bank vault. Plate + off-centre seam may clip through.',"
)
# The settings overlay gets a fifth slider while retaining the E4.1 folder picker.
interface_needle = '''class F1Interface(E57Interface):
    """F1.5 display: five persistent game sliders; Kitty route and E5.7 comments retained."""

    def _draw_header(self):
'''
interface_replacement = '''class F1Interface(E57Interface):
    """F1.5 display: five persistent game sliders; Kitty route and E5.7 comments retained."""

    def _d1_hint(self, g):
        if not g.c1_hint_visible:
            return ''
        if g.current_area_id == 'castle_hall':
            return ('CASTLE HALL: LEFT → Mage Room  |  MIDDLE → outside  |  RIGHT → bank vault (point + E). '
                    'A carried plate and the off-centre seam still hide the vault route.')
        return super()._d1_hint(g)

    def _draw_c13_game_config(self, surface, g):
        shade = pygame.Surface((GAME_WIDTH, GAME_HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 153))
        surface.blit(shade, (0, 0))
        panel = pygame.Rect(305, 52, 670, 558)
        pygame.draw.rect(surface, (25, 24, 33), panel, border_radius=13)
        pygame.draw.rect(surface, (231, 181, 117), panel, 3, border_radius=13)
        self._c1_text(surface, 'GAME CONFIGURATION', 345, 71, (255, 226, 166), self.game_font, 490)
        close = pygame.Rect(C13_GAME_CLOSE)
        pygame.draw.rect(surface, (100, 58, 58), close, border_radius=6)
        self._c1_text(surface, 'CLOSE', close.x+6, close.y+11, (255, 232, 213), self.game_small_font, 54)
        values = (self.machine.soup_speed_multiplier, self.machine.soup_effect_seconds,
                  self.machine.hidden_chest_hitbox_scale, self.machine.bubble_duration_seconds,
                  self.machine.special_hard_hitbox)
        labels = ('Soup speed multiplier', 'Soup effect duration',
                  'Hidden chest hitbox size ONLY', 'Speech bubble duration',
                  'Special Hard Hitbox — platter / vault seam')
        displays = (f'{values[0]:.1f}x normal speed', f'{values[1]} seconds',
                    f'{values[2]:.2f}x chest width and height', f'{values[3]:.1f} seconds',
                    f'{values[4]:.1f} / 5.0  (higher = smaller, harder target)')
        for i, (x, y, w, h) in enumerate(F15_SLIDER_TRACKS):
            self._c1_text(surface, labels[i], x, y-47, (248, 228, 191), self.game_font, 480)
            self._c1_text(surface, displays[i], x, y-22, (162, 244, 183), self.game_small_font, 470)
            pygame.draw.rect(surface, (73, 67, 78), (x, y, w, h), border_radius=6)
            lo, hi = F15_SLIDER_RANGES[i]
            t = max(0.0, min(1.0, (values[i]-lo)/(hi-lo)))
            pygame.draw.rect(surface, (148, 206, 132), (x, y, max(5, round(w*t)), h), border_radius=6)
            knob = pygame.Rect(round(x+w*t)-10, y-7, 20, 29)
            pygame.draw.rect(surface, (247, 213, 146), knob, border_radius=5)
            if g.c13_slider_selected == i:
                pygame.draw.rect(surface, (255, 255, 242), knob, 2, border_radius=5)
        self._c1_text(surface, 'Special Hard Hitbox changes only the off-centre plate target. 1 = forgiving; 5 = precise.',
                      345, 510, (225, 216, 204), self.game_small_font, 595)
        pygame.draw.rect(surface, (25, 24, 33), (332, 553, 619, 66), border_radius=5)
        pygame.draw.line(surface, (120, 103, 83), (339, 552), (935, 552))
        preferred = self.machine.config.get('log_directory', '')
        pretty = 'LOG PATH: ' + preferred
        font = self.game_small_font
        while font.size(pretty)[0] > 573 and len(pretty) > 14:
            pretty = pretty[:-2] + '…'
        self._c1_text(surface, pretty, 344, 557, (220, 217, 196), font, 582)
        folder = self.machine.config.get('log_folder_name', '')
        self._c1_text(surface, 'Browser folder: ' + (folder or 'not authorized (uses Downloads)'),
                      344, 589, (176, 213, 196), font, 398)
        button = pygame.Rect(E41_FOLDER_RECT)
        pygame.draw.rect(surface, (57, 82, 76), button, border_radius=5)
        pygame.draw.rect(surface, (204, 193, 141), button, 2, border_radius=5)
        self._c1_text(surface, 'CHOOSE FOLDER', button.x+8, button.y+6,
                      (247, 235, 184), font, button.width-16)

    def _draw_header(self):
'''
assert interface_needle in src
src = src.replace(interface_needle, interface_replacement, 1)
assert 'VERSION = "F1.5"' in src and 'SGGF1.5:' in src and 'F1.5  |' in src
MAIN.write_text(src, encoding='utf-8')
page = BASE_PLAY.read_text(encoding='utf-8')
for old, new in (("SGGF1.4", "SGGF1.5"), ("F1.4", "F1.5"), ("sggf14", "sggf15")):
    page = page.replace(old, new)
assert 'sggf15.apk' in page and 'sggf15.tar.gz' in page and 'archive:"sggf15"' in page
(HERE / 'F1_play.html').write_text(page, encoding='utf-8')

# ---------------------------------------------------------------------------
# 2. Replace the Hall background and the right-hand locked-door recipe.
# ---------------------------------------------------------------------------
doc = json.loads(ASSETS.read_text(encoding='utf-8'))
assert doc['version'] == 'SGGF1.4'
# Use the existing approved F1.5 hall background generator; it preserves all
# other art recipes/world entries and has already been preview-tested.
# Its code imports this same JSON, so produce the scene recipe through a clean
# controlled draw based on the same design primitives.

# Recreate the approved art recipe by executing the previous preview script,
# then read back its JSON as the base for the vault door adjustment.
import runpy
runpy.run_path(str(HERE / 'build_f15_hall_preview.py'))
preview_doc = json.loads((HERE / 'luma_assets_f15_preview.json').read_text(encoding='utf-8'))

# The bank vault: a heavy inset steel door with perimeter bolts, a circular
# multi-spoke locking wheel and a single stout release lever. All primitives
# are supported by Luma Draw Engine (no custom renderer required).
V = []
def vr(x,y,w,h,c,b=0,r=0):
    d={'op':'rect','rect':[int(x),int(y),int(w),int(h)],'color':list(c)}
    if b:d['border']=int(b)
    if r:d['radius']=int(r)
    V.append(d)
def vl(a,b,c,w=2): V.append({'op':'line','points':[[int(a[0]),int(a[1])],[int(b[0]),int(b[1])]],'color':list(c),'width':int(w)})
def vc(x,y,r,c,b=0):
    d={'op':'circle','center':[int(x),int(y)],'radius':int(r),'color':list(c)}
    if b:d['border']=int(b)
    V.append(d)
def vp(points,c,b=0):
    d={'op':'polygon','points':[[int(x),int(y)] for x,y in points],'color':list(c)}
    if b:d['border']=int(b)
    V.append(d)

steel0=(25,31,34); steel1=(51,61,64); steel2=(83,96,98); steel3=(128,141,138)
steel4=(173,181,166); bright=(211,211,188); dark=(15,20,22); gold=(174,139,78)
# Outer frame and recessed slab.
vr(0,0,130,166,steel0)
vr(4,4,122,158,steel2,3)
vr(9,9,112,148,steel1)
vr(14,14,102,138,steel3,2)
vr(19,19,92,128,steel0)
vr(23,23,84,120,steel2,2)
vr(28,28,74,110,steel1)
# Reinforced top/bottom horizontal plates.
vr(30,31,70,7,steel3)
vl((32,33),(98,33),bright,1)
vr(30,128,70,7,steel3)
vl((32,130),(98,130),bright,1)
# Six visible locking bolts around the slab.
for x,y in ((19,19),(111,19),(19,147),(111,147),(65,14),(65,152)):
    vc(x,y,5,dark)
    vc(x,y,3,steel4)
    vl((x-2,y),(x+2,y),steel1,1)
# Main radial wheel at left-centre, with bevelled housing.
vc(57,83,38,dark)
vc(57,83,34,steel4,3)
vc(57,83,29,steel1,2)
vc(57,83,24,steel3,2)
vc(57,83,18,steel0)
# Eight spokes converge on a solid hub.
for angle in range(0,360,45):
    a=math.radians(angle)
    x1=57+19*math.cos(a); y1=83+19*math.sin(a)
    x2=57+31*math.cos(a); y2=83+31*math.sin(a)
    vl((x1,y1),(x2,y2),bright,4)
    vl((x1,y1+1),(x2,y2+1),steel2,1)
vc(57,83,10,steel4,2)
vc(57,83,4,gold)
# Separate central hub cover and a small handle bar on the wheel.
vl((40,83),(74,83),steel0,4)
vl((57,66),(57,100),steel0,4)
vc(57,83,6,bright,2)
# A stout operating lever mounted on the right side; no excessive micro-detail.
vr(100,58,18,54,steel0)
vr(103,61,12,48,steel3,2)
vc(109,65,7,steel1,2)
vl((109,65),(116,42),steel4,7)
vc(117,40,7,steel0)
vc(117,40,4,gold)
# Small hinge/lock pins down the side and light-catching bevels.
for y in (45,83,121):
    vr(95,y-5,8,10,steel4,1)
    vc(99,y,2,steel0)
vl((26,43),(26,122),steel4,1)
vl((104,43),(104,122),steel0,2)
# Tiny access key slot below the wheel hub; it is decorative and non-functional.
vr(50,139,14,5,steel0)
vc(57,141,2,gold)

preview_doc['assets']['locked_door'] = {'width':130,'height':166,'commands':V}
preview_doc['version'] = 'SGGF1.5'
preview_doc['notes'] = (preview_doc.get('notes','').rstrip() +
    '\nSGGF1.5: Castle Hall stonework is aligned with the F1.4 Castle Exterior. The left Mage Room doorway and central return-to-exterior doorway retain their original objects, walk triggers and destinations. The right locked-door object is redrawn as a bank vault with a multi-spoke wheel and operating lever; it is interactable through dialogue but can never open. The existing platter-to-vault seam remains a separate hidden clip route with an off-centre, persistent Special Hard Hitbox setting.')

# Only change the approved hall background art, vault door art, vault object
# name/visual bounds/activity, version and notes. Keep doors and connections.
preview_doc['world']['objects'] = [
    ({**o, 'name':'Bank Vault Door', 'x':918, 'y':244, 'width':130, 'height':166, 'activity':'vault_interact'}
     if o.get('object_id') == 'vault_locked_door' else o)
    for o in preview_doc['world']['objects']
]
ASSETS.write_text(json.dumps(preview_doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# Recreate the preview from the final F1.5 JSON, so both assets and object
# geometry are visible in the exact scene that is being packaged.
AS = preview_doc['assets']
W,H = 1280,640
im=Image.new('RGBA',(W,H),(0,0,0,255))
def render_asset(name,x=0,y=0,w=None,h=None):
    a=AS[name]; w=w or a['width']; h=h or a['height']; sx=w/a['width']; sy=h/a['height']; dr=ImageDraw.Draw(im)
    for c in a['commands']:
        op=c['op']; col=tuple(c.get('color',(255,255,255)))
        width=max(1,round(c.get('width',1)*(abs(sx)+abs(sy))/2)); border=max(0,round(float(c.get('border',0))*(abs(sx)+abs(sy))/2))
        if op in ('rect','ellipse'):
            rx,ry,rw,rh=c['rect']; box=(x+rx*sx,y+ry*sy,x+(rx+rw)*sx,y+(ry+rh)*sy)
            if op=='rect':
                if border: dr.rectangle(box,outline=col,width=border)
                else: dr.rectangle(box,fill=col)
            else:
                if border: dr.ellipse(box,outline=col,width=border)
                else: dr.ellipse(box,fill=col)
        elif op=='polygon':
            pts=[(x+px*sx,y+py*sy) for px,py in c['points']]
            if border: dr.line(pts+[pts[0]],fill=col,width=border,joint='curve')
            else: dr.polygon(pts,fill=col)
        elif op=='line':
            pts=[(x+px*sx,y+py*sy) for px,py in c['points']]
            dr.line(pts,fill=col,width=width,joint='curve')
        elif op=='circle':
            cx,cy=c['center']; r=c['radius']*(sx+sy)/2; box=(x+cx*sx-r,y+cy*sy-r,x+cx*sx+r,y+cy*sy+r)
            if border: dr.ellipse(box,outline=col,width=border)
            else: dr.ellipse(box,fill=col)
render_asset('c1_bg_castle_hall')
for oid in ('lab_door','castle_exit','vault_locked_door','vault_wall_seam'):
    obj=next(o for o in preview_doc['world']['objects'] if o['object_id']==oid)
    render_asset(obj['kind'],obj['x'],obj['y'],obj['width'],obj['height'])
render_asset('player',620,469,40,58)
dr=ImageDraw.Draw(im)
dr.rectangle((0,0,1280,44),fill=(22,18,31)); dr.line((0,43,1280,43),fill=(187,145,83),width=2)
try: font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16); small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',13)
except: font=ImageFont.load_default(); small=font
dr.text((15,12),"SPIFFY'S GIFT  |  F1.5 CASTLE HALL  |  BROWSER",font=font,fill=(239,225,195))
dr.rectangle((0,614,1280,640),fill=(35,28,31)); dr.line((0,614,1280,614),fill=(166,133,91),width=2)
dr.text((14,620),'LEFT: MAGE ROOM  |  MIDDLE: OUTSIDE  |  RIGHT: BANK VAULT (point + E)  |  PLATE + OFF-CENTRE SEAM',font=small,fill=(245,236,214))
preview_path = HERE/'F1.5_CASTLE_HALL_PREVIEW.png'
im.convert('RGB').save(preview_path,quality=95)
(HERE/'luma_assets_f15_preview.json').write_text(json.dumps(preview_doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('PATCHED MAIN', MAIN, len(src))
print('PATCHED ASSETS', ASSETS, len(preview_doc['assets']['c1_bg_castle_hall']['commands']), 'hall commands;', len(V), 'vault commands')
print('PREVIEW', preview_path)
