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
assert main.VERSION == 'F1.3'
assert 'machine = F1StateMachine(archive, config, warning)' in src
assert 'ui = F1Interface(machine)' in src
assert 'class F1GameModel(E56GameModel)' in src
assert 'class F1StateMachine(E57StateMachine)' in src
assert 'class F1Interface(E57Interface)' in src

assets = json.loads((HERE / 'luma_assets_e33.json').read_text(encoding='utf-8'))
base = json.loads((HERE / 'F1.1_BASE_LUMA_ASSETS.json').read_text(encoding='utf-8'))
assert assets['version'] == 'SGGF1.3'
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
print('PASS F1.3 syntax, Luma recipe/world validation, preserved Stables/Kitty/Part One, save migration and mobile front-door gate.')


# F1.3 scope lock: compare the complete asset document to F1.2 with only
# the three-pass temporary guide line, release version/notes, and return landing changed.
from copy import deepcopy
f12 = json.loads((HERE / 'F1.2_BASE_LUMA_ASSETS.json').read_text(encoding='utf-8'))
expected = deepcopy(f12)
expected['version'] = 'SGGF1.3'
path_commands = expected['assets']['c1_bg_castle_path']['commands']
removed = [c for c in path_commands
           if c.get('op') == 'line'
           and c.get('points') == [[748,435],[834,307]]]
assert len(removed) == 3, f'F1.2 guide line should be exactly three draw passes, found {len(removed)}'
expected['assets']['c1_bg_castle_path']['commands'] = [
    c for c in path_commands
    if not (c.get('op') == 'line' and c.get('points') == [[748,435],[834,307]])
]
reverse_expected = next(c for c in expected['world']['connections']
                        if c['connection_id'] == 'castle_exterior_bottom_castle_path')
reverse_expected['arrival_x'] = 834
reverse_expected['arrival_y'] = 400
expected['notes'] = (expected.get('notes', '').rstrip() +
    '\nSGGF1.3: removed the temporary Castle Path threshold guide stroke, added a visible Castle Exterior direction arrow beyond the unchanged invisible crossing threshold, and moved the Castle Exterior return landing safely onto the Castle Path approach. All other F1.2 assets, areas, gameplay, and transition logic are retained.')
assert assets == expected, 'An asset/world change occurred outside the explicit F1.3 scope.'
assert all(not (c.get('op') == 'line' and c.get('points') == [[748,435],[834,307]])
           for c in assets['assets']['c1_bg_castle_path']['commands'])

# The physical crossing-state machine and castle-path model remain byte-for-byte F1.2.
f12_main = (HERE / 'F1.2_BASE_MAIN.py').read_text(encoding='utf-8')
def class_block(text, class_name):
    start = text.index(f'class {class_name}')
    end = text.find('\nclass ', start + 1)
    return text[start:] if end < 0 else text[start:end]
assert class_block(src, 'E56StateMachine') == class_block(f12_main, 'E56StateMachine')
assert class_block(src, 'E56GameModel') == class_block(f12_main, 'E56GameModel')
assert 'before_progress < 0.0 <= after_progress and abs(lateral) <= 43.0' in src

# The visual marker sits castle-ward of the invisible threshold and points along
# the exact E5.6 approach vector; it is not the trigger.
approach = main.E56StateMachine.CASTLE_APPROACH
forward = main.E56StateMachine.CASTLE_FORWARD
lateral = main.E56StateMachine.CASTLE_LATERAL
marker_xy = (approach[0] + forward[0] * 40.0,
             approach[1] + forward[1] * 40.0)
marker_progress = ((marker_xy[0]-approach[0])*forward[0]
                   + (marker_xy[1]-approach[1])*forward[1])
marker_lateral = ((marker_xy[0]-approach[0])*lateral[0]
                  + (marker_xy[1]-approach[1])*lateral[1])
assert marker_progress > 35 and abs(marker_lateral) < 0.01
arrow_method = src[src.index('    def _draw_edge_arrows(self,surface,g):'):
                   src.index('    def _c1_text(self,surface,s,x,y,color,font,width):')]
assert 'castle_path_top_castle_exterior' in arrow_method
assert 'E56StateMachine.CASTLE_FORWARD' in arrow_method
assert 'E56StateMachine.CASTLE_LATERAL' in arrow_method
assert "name=g.areas[conn.to_area_id].display_name" in arrow_method
castle_exterior_area = next(a for a in assets['world']['areas'] if a['area_id'] == 'castle_exterior')
assert castle_exterior_area['display_name'] == 'Castle Exterior'

# Exercise the real model return transition and prove it lands well behind the
# invisible threshold, on the center of the approach corridor, without snapping.
# This headless build test needs only the Rect constructor; Castle Path has no solids.
class _TestRect:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.width, self.height = x, y, w, h
main.pygame = type('PygameStub', (), {'Rect': _TestRect})
return_game = main.F1GameModel(engine)
return_game.current_area_id = 'castle_exterior'
return_game.player_x, return_game.player_y = 640.0, 500.0
return_connection = return_game.activate_connection('edge', edge='bottom')
assert return_connection is not None
assert return_connection.connection_id == 'castle_exterior_bottom_castle_path'
assert return_game.current_area_id == 'castle_path'
assert abs(return_game.player_x - 834.0) < 0.01
assert abs(return_game.player_y - 400.0) < 0.01
return_progress = ((return_game.player_x-approach[0])*forward[0]
                   + (return_game.player_y-approach[1])*forward[1])
return_lateral = ((return_game.player_x-approach[0])*lateral[0]
                  + (return_game.player_y-approach[1])*lateral[1])
assert return_progress < -45 and abs(return_lateral) < 2
assert return_game._e3_nav_error(return_game.player_x, return_game.player_y) <= 1.0

# The modified reverse-spawn coordinate also remains a valid edge-marker lookup
# for the unchanged forward crossing across the full authored lateral tolerance.
for lateral_offset in (-43.0, 0.0, 43.0):
    crossing_game = main.F1GameModel(engine)
    crossing_game.current_area_id = 'castle_path'
    crossing_game.player_x = approach[0] + lateral[0]*lateral_offset
    crossing_game.player_y = approach[1] + lateral[1]*lateral_offset
    found = crossing_game.connection_for('edge', edge='top')
    assert found is not None and found.connection_id == 'castle_path_top_castle_exterior'
print('PASS F1.3 scope lock: only guide-line removal, Castle Exterior marker, release labels, and safe return placement differ from F1.2; original crossing trigger and all Stables/Part One behavior remain unchanged.')
