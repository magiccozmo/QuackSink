"""F1.5 release checks: Castle Hall/vault scope, dialogue and adjustable plate hitbox."""
from pathlib import Path
import copy
import json
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import main

class FakeRect:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.width, self.height = float(x), float(y), float(w), float(h)
    def inflate(self, dx, dy):
        return FakeRect(self.x-dx/2, self.y-dy/2, self.width+dx, self.height+dy)
    def collidepoint(self, *point):
        if len(point) == 2:
            px, py = point
        else:
            px, py = point[0]
        return self.x <= px < self.x+self.width and self.y <= py < self.y+self.height

# The tests need only Rect semantics; the real game imports pygame in main().
main.pygame = SimpleNamespace(Rect=FakeRect)

source = (HERE / 'main.py').read_text(encoding='utf-8')
assert main.VERSION == 'F1.5'
assert 'class F1GameModel(E56GameModel)' in source
assert 'class F1StateMachine(E57StateMachine)' in source
assert 'class F1Interface(E57Interface)' in source
assert 'Special Hard Hitbox' in source
assert 'SGGF1.5:' in source

# Config validation keeps the new setting independent and bounded.
assert main.CONFIG_DEFAULTS['special_hard_hitbox'] == 3.0
assert main._normalized_config({})['special_hard_hitbox'] == 3.0
assert main._normalized_config({'special_hard_hitbox': 99})['special_hard_hitbox'] == 5.0
assert main._normalized_config({'special_hard_hitbox': -2})['special_hard_hitbox'] == 1.0
assert main._normalized_config({'special_hard_hitbox': 'not a number'})['special_hard_hitbox'] == 3.0

# Luma accepts every asset command; F1.4 baseline provides a full scope comparator.
assets = json.loads((HERE / 'luma_assets_e33.json').read_text(encoding='utf-8'))
base = json.loads((HERE / 'F1.4_BASE_LUMA_ASSETS.json').read_text(encoding='utf-8'))
assert assets['version'] == 'SGGF1.5'
engine = main.LumaDrawEngine(HERE / 'luma_assets_e33.json')
assert all(cmd['op'] in main.LumaDrawEngine.SUPPORTED_OPS
           for asset in assets['assets'].values() for cmd in asset['commands'])

# JSON diff is limited to the hall backdrop, vault artwork, vault object geometry/name,
# release version and release notes. All other areas, props, and world rules match F1.4.
expected = copy.deepcopy(base)
expected['version'] = assets['version']
expected['notes'] = assets['notes']
expected['assets']['c1_bg_castle_hall'] = assets['assets']['c1_bg_castle_hall']
expected['assets']['locked_door'] = assets['assets']['locked_door']
base_vault = next(o for o in expected['world']['objects'] if o['object_id'] == 'vault_locked_door')
new_vault = next(o for o in assets['world']['objects'] if o['object_id'] == 'vault_locked_door')
base_vault.update({k: new_vault[k] for k in ('name','x','y','width','height','activity')})
assert assets == expected, 'F1.5 changed JSON outside the Castle Hall/vault release scope.'
assert len(assets['assets']['c1_bg_castle_hall']['commands']) >= 600
assert assets['assets']['locked_door']['width'] == 130
assert len(assets['assets']['locked_door']['commands']) >= 65

# The left Mage door and middle outside door retain their exact positions/triggers.
base_objs = {o['object_id']: o for o in base['world']['objects']}
objs = {o['object_id']: o for o in assets['world']['objects']}
for oid in ('lab_door', 'castle_exit', 'vault_wall_seam'):
    assert objs[oid] == base_objs[oid], f'{oid} changed from F1.4'
assert objs['vault_locked_door']['kind'] == 'locked_door'
assert objs['vault_locked_door']['name'] == 'Bank Vault Door'
base_connections = {c['connection_id']: c for c in base['world']['connections']}
connections = {c['connection_id']: c for c in assets['world']['connections']}
for cid in ('castle_hall_to_castle_exterior', 'castle_hall_to_mages_lab',
            'castle_hall_to_vault_clip', 'castle_exterior_to_castle_hall',
            'mages_lab_to_castle_hall', 'vault_to_hall'):
    assert connections[cid] == base_connections[cid], f'Connection changed: {cid}'
assert not any(c.get('from_area_id') == 'castle_hall'
               and c.get('source_object_id') == 'vault_locked_door'
               and c.get('trigger') == 'door' for c in connections.values())

# All three hall approaches and the offset clip location are inside the existing walkable region.
game = main.F1GameModel(engine)
game.current_area_id = 'castle_hall'
assert game.can_move_to(296, 412), 'Mage Room door threshold is not reachable.'
assert game.can_move_to(640, 426), 'Central exterior threshold is not reachable.'
assert game.can_move_to(1046, 333), 'Off-centre platter target is not reachable.'

# The vault object is now a mouse target, while still remaining a locked_door kind.
vault = game.object_by_id('vault_locked_door')
assert vault is not None and vault.kind == 'locked_door'
assert game.hit_test((vault.x+vault.width/2, vault.y+vault.height/2)) is vault

# Off-centre hitbox starts forgiving and becomes smaller/harder, without moving to the door centre.
sm = object.__new__(main.F1StateMachine)
sm.game = game
sm.special_hard_hitbox = 1.0
box_easy = sm._f15_plate_clip_rect()
sm.special_hard_hitbox = 5.0
box_hard = sm._f15_plate_clip_rect()
assert box_easy.width > box_hard.width and box_easy.height > box_hard.height
assert abs((box_hard.x+box_hard.width/2) - (vault.x+vault.width/2)) > 45
assert abs((box_hard.y+box_hard.height/2) - (vault.y+vault.height/2)) < 20

# The hidden route still requires a carried plate and movement toward the seam.
plate = game.c1_make_item('Iron Plate', 'plate')
game.carried_object_id = plate.object_id
plate.in_inventory = False
sm.special_hard_hitbox = 3.0
box = sm._f15_plate_clip_rect()
game.player_x = box.x + box.width/2
game.player_y = box.y + box.height/2
assert sm._plate_clip_trigger(game, 1) is True
assert sm._plate_clip_trigger(game, 0) is False
assert sm._plate_clip_trigger(game, -1) is False
other = game.c1_make_item('Turnip', 'vegetable')
game.carried_object_id = other.object_id
assert sm._plate_clip_trigger(game, 1) is False
# Remove the decoy item so the menu test starts with a predictable two-item pack.
game.c1_consume(other)
plate.in_inventory = True
game.carried_object_id = None

# Test real F1 dialogue dispatch through a lightweight instance harness.
sm.game = game
sm.f15_vault_inventory_page = 0
sm.logs = []
sm._log = lambda *args: sm.logs.append(args)
sm._dialogue = lambda speaker, line, options: setattr(game, 'c1_dialogue', {
    'speaker': speaker, 'line': line, 'options': options[:5]})
sm._speech = lambda message, seconds=4: setattr(sm, 'last_speech', message)
sm._f15_vault_main_dialogue()
assert [o['text'] for o in game.c1_dialogue['options']] == ['Pick lock', 'Force open', 'Leave the vault alone']
sm._choose_dialogue(0)
assert "Are you kidding? Even the Skeleton Key ain't gonna pick this." in game.c1_dialogue['line']
sm._f15_vault_main_dialogue()
sm._choose_dialogue(1)
assert 'what should i force it open with?' in game.c1_dialogue['speaker'].lower()
assert len(game.c1_dialogue['options']) <= 5
plate_options = [o for o in game.c1_dialogue['options'] if o['action'] == 'f15_vault_item:' + plate.object_id]
assert plate_options, 'Carried plate not selectable from the inventory dialogue.'
plate_index = game.c1_dialogue['options'].index(plate_options[0])
sm._choose_dialogue(plate_index)
assert 'Oddly the plate ALMOST squeezes in a gap.' in game.c1_dialogue['line']
assert game.c1_vault_entered is False
assert vault.area_id == 'castle_hall'

# The vault remains permanently locked for varied items as well.
gold = game.c1_make_item('Bag of Gold', 'gold')
sm._f15_vault_force_open = lambda: sm._f15_vault_inventory_dialogue(0)
sm._f15_vault_main_dialogue(); sm._choose_dialogue(1)
gold_option = next(i for i,o in enumerate(game.c1_dialogue['options'])
                   if o['action'] == 'f15_vault_item:' + gold.object_id)
sm._choose_dialogue(gold_option)
assert 'already full of money' in game.c1_dialogue['line']
assert vault.area_id == 'castle_hall' and game.c1_vault_entered is False

# The new setting is persisted via the existing main config route.
sm.special_hard_hitbox = 3.0
persisted = []
sm.persist_preference = lambda key, value: persisted.append((key,value)) or None
sm._f15_set_special_hard_hitbox(4.2)
assert sm.special_hard_hitbox == 4.2
assert persisted == [('special_hard_hitbox', 4.2)]

# Web launcher points only at the matching F1.5 browser archive.
page = (HERE / 'F1_play.html').read_text(encoding='utf-8')
assert all(s in page for s in ('SGGF1.5', 'sggf15.apk', 'sggf15.tar.gz', 'archive:"sggf15"'))
assert 'sggf14' not in page
print('PASS F1.5 syntax, Luma validation, F1.4 scope diff, hall navigation/door transitions, off-centre hitbox, vault inventory dialogue, and persistent setting.')
