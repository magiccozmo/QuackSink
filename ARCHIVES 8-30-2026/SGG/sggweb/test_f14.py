"""SGGF1.3 regression checks: independent Stables assets, save migration and F1.0 gameplay retention."""
from pathlib import Path
import ast
import copy
import json
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import main

src = (HERE / 'main.py').read_text(encoding='utf-8')
ast.parse(src)
assert main.VERSION == 'F1.4'
assert 'machine = F1StateMachine(archive, config, warning)' in src
assert 'ui = F1Interface(machine)' in src
assert 'class F1GameModel(E56GameModel)' in src
assert 'class F1StateMachine(E57StateMachine)' in src
assert 'class F1Interface(E57Interface)' in src

assets = json.loads((HERE / 'luma_assets_e33.json').read_text(encoding='utf-8'))
base = json.loads((HERE / 'F1.1_BASE_LUMA_ASSETS.json').read_text(encoding='utf-8'))
assert assets['version'] == 'SGGF1.4'
assert len(assets['assets']['c1_bg_stables']['commands']) == 648
assert all(op.get('op') in main.LumaDrawEngine.SUPPORTED_OPS
           for a in assets['assets'].values() for op in a['commands'])

# Kitty's four animation recipes are bit-for-bit unchanged from F1.1 (and F1.0).
for key in ('kitty_walk_a', 'kitty_walk_b', 'kitty_sit', 'kitty_sit_blink'):
    assert assets['assets'][key] == base['assets'][key], f'Kitty art changed: {key}'
assert assets['assets']['sammich']['width'] == 82

# The Stables geometry and the full background recipe are unchanged from F1.1.
base_areas = {a['area_id']: a for a in base['world']['areas']}
areas = {a['area_id']: a for a in assets['world']['areas']}
stables = areas['stables']
base_stables = base_areas['stables']
for key in ('background_asset', 'vendors', 'solid_rects', 'sight_blockers', 'conceal_zones', 'navigation'):
    assert stables.get(key) == base_stables.get(key), f'Stables geometry changed: {key}'
assert assets['assets']['c1_bg_stables']['commands'] == base['assets']['c1_bg_stables']['commands']

# Carriage and fence recipes are byte-for-byte unchanged from F1.1.
assert assets['assets']['stable_carriage'] == base['assets']['stable_carriage']
assert assets['assets']['stables_foreground_fence'] == base['assets']['stables_foreground_fence']

# Every outline-only horse polygon now has a matching fill command immediately before it.
base_horse = base['assets']['stable_draft_horse']['commands']
expected_horse = []
for command in base_horse:
    if command.get('op') == 'polygon' and int(command.get('border', 0) or 0) > 0:
        fill = copy.deepcopy(command)
        fill['border'] = 0
        expected_horse.extend((fill, copy.deepcopy(command)))
    else:
        expected_horse.append(copy.deepcopy(command))
assert assets['assets']['stable_draft_horse']['commands'] == expected_horse
horse_commands = assets['assets']['stable_draft_horse']['commands']
assert len(horse_commands) == 79
for i, command in enumerate(horse_commands):
    if command.get('op') == 'polygon' and int(command.get('border', 0) or 0) > 0:
        fill = horse_commands[i - 1]
        assert fill.get('op') == 'polygon' and int(fill.get('border', 0) or 0) == 0
        assert fill.get('points') == command.get('points') and fill.get('color') == command.get('color')
assert all(c['op'] in main.LumaDrawEngine.SUPPORTED_OPS for c in horse_commands)

new_ids = {'stable_carriage', 'stable_draft_horse', 'stables_foreground_fence'}
objs = {o['object_id']: o for o in assets['world']['objects']}
assert new_ids <= set(objs)
for oid in new_ids:
    o = objs[oid]
    assert o['area_id'] == 'stables' and o['kind'] in assets['assets']
    assert o['takeable'] is False and o['stealable'] is False and o['on_shelf'] is False

# Renderer draws the foreground fence before the horse, with vendor and player on top.
renderer = src[src.index('class LumaInterface'):src.index('class',src.index('class LumaInterface')+10)]
assert "('stable_carriage', 'stables_foreground_fence', 'stable_draft_horse')" in renderer
assert 'prop.kind, prop.rect()' in renderer
assert "if obj.object_id in ('stable_carriage', 'stable_draft_horse', 'stables_foreground_fence')" in renderer
assert src.index('engine.draw_asset(surface, prop.kind, prop.rect())') < src.index('for v in g.current_area.vendors:')

# Instantiate the real model against F1.3 JSON; the draw engine validates every recipe.
engine = main.LumaDrawEngine(HERE / 'luma_assets_e33.json')
game = main.F1GameModel(engine)
game.f1_prepare_state()
assert game.areas['stables'].vendors[0]['recipe'] == 'carriage_driver'
assert new_ids <= {o.object_id for o in game.objects}
assert sum(1 for o in game.objects if o.area_id == 'stables' and o.object_id in new_ids) == 3
sammich = game.c1_make_item('Egg McGuffin Sammich', 'sammich', price=0)
assert (sammich.width, sammich.height) == (82, 60)
game.c1_consume(sammich)
game.c1_flags['driver_fed'] = True
game.c1_flags['carriage_unlocked'] = True
game.f1_prepare_state()
vendors = {v['vendor_id']: v for v in game.areas['stables'].vendors}
assert vendors['carriage_driver']['recipe'] == 'carriage_driver_happy'
assert vendors['cozmo_part_one']['recipe'] == 'cozmo_magician'

# F1.0 save migration: missing static scenery is added without touching flags/items/player state.
snapshot = game.snapshot()
snapshot['source_version'] = 'F1.0'
snapshot['objects'] = [o for o in snapshot['objects'] if o['object_id'] not in new_ids]
for oid in new_ids: snapshot['item_meta'].pop(oid, None)
loaded = main.C131GameModel.from_snapshot(engine, snapshot)
loaded.__class__ = main.F1GameModel
loaded.f1_prepare_state()
assert new_ids <= {o.object_id for o in loaded.objects}
assert new_ids <= set(loaded.item_meta)
assert loaded.c1_flags['driver_fed'] is True
assert loaded.c1_flags['carriage_unlocked'] is True
loaded_vendors = {v['vendor_id']: v for v in loaded.areas['stables'].vendors}
assert loaded_vendors['carriage_driver']['recipe'] == 'carriage_driver_happy'
assert 'cozmo_part_one' in loaded_vendors
assert loaded.c1_gold == game.c1_gold
assert loaded.inventory == game.inventory

# Exercise the actual F1 dialogue handlers with a lightweight state-machine harness.
sm = object.__new__(main.F1StateMachine)
sm.game = game
sm.d11_context_ref = None
sm.logs = []
sm._log = lambda *args: sm.logs.append(args)
sm._dialogue = lambda speaker, line, options: setattr(game, 'c1_dialogue',
    {'speaker': speaker, 'line': line, 'options': options[:5]})
sm._speech = lambda message, seconds=4: setattr(sm, 'last_speech', message)
for v in game.areas['stables'].vendors[:]:
    if v.get('vendor_id') == 'cozmo_part_one': game.areas['stables'].vendors.remove(v)
game.c1_flags.update({'driver_fed': False, 'carriage_unlocked': False, 'cozmo_finale_seen': False})
game.f1_prepare_state()
item = game.c1_make_item('Egg McGuffin Sammich', 'sammich', price=0)
driver = next(v for v in game.areas['stables'].vendors if v['vendor_id'] == 'carriage_driver')
sm._talk_vendor(driver)
assert game.c1_dialogue['options'][0]['action'] == 'f1_feed_driver'
sm._choose_dialogue(0)
assert game.c1_flags['driver_fed'] and game.c1_flags['carriage_unlocked']
assert item.area_id == '__consumed__'
assert any(v['vendor_id'] == 'cozmo_part_one' for v in game.areas['stables'].vendors)
cozmo = next(v for v in game.areas['stables'].vendors if v['vendor_id'] == 'cozmo_part_one')
sm._talk_vendor(cozmo)
assert 'END OF PART ONE' in game.c1_dialogue['line']
for action in ('f1_cozmo_page2', 'f1_cozmo_page3', 'f1_cozmo_page4', 'f1_cozmo_finish'):
    game.c1_dialogue = {'speaker': 'Cozmo', 'line': '', 'options': [{'text': 'Continue', 'action': action}]}
    sm._choose_dialogue(0)
assert game.c1_flags['cozmo_finale_seen'] is True

# Fearmonger continues to grant 5,000 gold and the sammich once.
reward_game = main.F1GameModel(engine)
reward_game.c1_flags['quest_started'] = True
potion = reward_game.c1_make_item('Potion of Increased Physical Enhancement', 'potion', price=69000)
reward_sm = object.__new__(main.F1StateMachine)
reward_sm.game = reward_game
reward_sm.d11_context_ref = None
reward_sm._log = lambda *args: None
reward_sm._speech = lambda message, seconds=4: setattr(reward_sm, 'last_speech', message)
reward_sm._dialogue = lambda speaker, line, options: setattr(reward_game, 'c1_dialogue',
    {'speaker': speaker, 'line': line, 'options': options[:5]})
fearmonger = {'npc_id': 'fearmonger', 'name': 'Fearmonger', 'area_id': 'mages_lab',
              'x': 640, 'y': 400, 'height': 80, 'alive': True}
reward_sm._talk(fearmonger)
assert reward_game.c1_flags['quest_done'] is True
assert reward_game.c1_gold == 5000
assert reward_game.c1_flags['egg_mcguffin_awarded'] is True
assert reward_game.c1_have(lambda o: o.kind == 'sammich') is not None
reward_count = sum(o.kind == 'sammich' and o.area_id != '__consumed__' for o in reward_game.objects)
reward_sm._talk(fearmonger)
assert sum(o.kind == 'sammich' and o.area_id != '__consumed__' for o in reward_game.objects) == reward_count

# Front-door mobile gating and catalog schema are preserved.
for name in ('index.html', 'versions.html'):
    page = (HERE / 'deploy' / name).read_text(encoding='utf-8')
    assert 'isPhoneOrTablet' in page and 'body.device-blocked main{display:none}' in page
    assert "navigator.userAgentData?.mobile" in page
    assert "Other devices may happen!" in page
    assert "^SGG[A-Z]\\d+(?:\\.\\d+)*$" in page
assert re.fullmatch(r'SGG[A-Z]\d+(?:\.\d+)*', 'SGGF1.3')
assert re.fullmatch(r'SGG[A-Z]\d+(?:\.\d+)*', 'SGGE5.7')
print('PASS F1.4 syntax, Luma recipe/world validation, preserved Stables/Kitty/Part One, save migration and mobile front-door gate.')


# F1.4 scope lock: compare the complete F1.4 JSON against the exact F1.3 base.
# The only authorized changes are the Castle Exterior background recipe,
# release version and appended release note. World/collision/gameplay data is unchanged.
from copy import deepcopy
f13 = json.loads((HERE / 'F1.3_BASE_LUMA_ASSETS.json').read_text(encoding='utf-8'))
expected = deepcopy(f13)
expected['version'] = 'SGGF1.4'
expected['assets']['c1_bg_castle_exterior'] = assets['assets']['c1_bg_castle_exterior']
expected['notes'] = (expected.get('notes', '').rstrip() +
    '\nSGGF1.4: rebuilt only the Castle Exterior background to match the F1.3 Castle Path castle: round pale-stone arch, deep vaulted opening, raised portcullis detail, open wooden gate leaves, square battlement towers, and a centered cobbled approach. Castle Path art, transitions, walkable corridor, entrance trigger, other scenes, gameplay, and save data are retained.')
assert assets == expected, 'F1.4 JSON changed something outside the Castle Exterior background and release metadata.'
assert assets['assets']['c1_bg_castle_path'] == f13['assets']['c1_bg_castle_path']
assert assets['assets']['c1_bg_castle_exterior']['width'] == 1280
assert assets['assets']['c1_bg_castle_exterior']['height'] == 640
assert len(assets['assets']['c1_bg_castle_exterior']['commands']) >= 850
assert all(c['op'] in main.LumaDrawEngine.SUPPORTED_OPS
           for c in assets['assets']['c1_bg_castle_exterior']['commands'])

# All world data remains byte-for-byte the F1.3 definition: movement, solids,
# nav regions, transition destinations, trigger and door object are untouched.
assert assets['world'] == f13['world'], 'F1.4 altered gameplay/world definitions.'
castle_exterior = next(a for a in assets['world']['areas'] if a['area_id'] == 'castle_exterior')
assert castle_exterior['solid_rects'] == [[214, 165, 336, 240], [745, 165, 328, 240]]
assert castle_exterior['navigation']['regions'] == [
    [[20, 408], [1260, 408], [1260, 623], [20, 623]],
    [[563, 322], [726, 322], [726, 445], [563, 445]],
]
castle_door = next(o for o in assets['world']['objects'] if o['object_id'] == 'castle_hall_door')
assert castle_door['kind'] == 'door'
assert castle_door['walk_trigger'] == {'rect': [582, 453, 111, 21], 'approach': 'north'}
assert castle_door['x'] == 589 and castle_door['y'] == 325

# F1.3 Castle Path to Castle Exterior arrival and return landing remain unchanged.
connections = {c['connection_id']: c for c in assets['world']['connections']}
assert connections['castle_path_top_castle_exterior']['arrival_x'] == 640
assert connections['castle_path_top_castle_exterior']['arrival_y'] == 510
assert connections['castle_exterior_bottom_castle_path']['arrival_x'] == 834
assert connections['castle_exterior_bottom_castle_path']['arrival_y'] == 400

# Only release labels/status strings differ in main.py; model/transition classes
# and all actual game logic remain identical to the F1.3 release.
f13_main = (HERE / 'F1.3_BASE_MAIN.py').read_text(encoding='utf-8')
def class_block(text, class_name):
    start = text.index(f'class {class_name}')
    end = text.find('\nclass ', start + 1)
    return text[start:] if end < 0 else text[start:end]
for class_name in ('E56StateMachine','E56GameModel','F1GameModel','F1StateMachine'):
    current_block = class_block(src, class_name)
    baseline_block = class_block(f13_main, class_name)
    if class_name == 'F1StateMachine':
        current_block = current_block.replace(
            "SGGF1.4: Castle Exterior matches the Castle Path fortress; all F1.3 gameplay and transitions retained.",
            "SGGF1.3: Castle Path transition marker and safe return; F1.2 Stables and Part One retained.")
    assert current_block == baseline_block, f'F1.4 changed {class_name} beyond release text.'
for old,new in (
    ('VERSION = "F1.3"  # Castle Path transition marker and safe return placement.',
     'VERSION = "F1.4"  # Castle Exterior architecture matched to the F1.3 Castle Path.'),
    ("self._set_status('SGGF1.3: Castle Path transition marker and safe return; F1.2 Stables and Part One retained.')",
     "self._set_status('SGGF1.4: Castle Exterior matches the Castle Path fortress; all F1.3 gameplay and transitions retained.')"),
    ('label = "SPIFFY\'S GIFT  |  F1.3  |  " + (\'BROWSER\' if BROWSER else \'DESKTOP\')',
     'label = "SPIFFY\'S GIFT  |  F1.4  |  " + (\'BROWSER\' if BROWSER else \'DESKTOP\')')):
    assert old not in src and new in src
print('PASS F1.4 scope lock: Castle Exterior art only; Castle Path, door trigger, navigation, collision, all transitions, gameplay, and save logic retained.')
