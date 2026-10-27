#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Spiffy's Gift - C1.0. Interactive sandbox adventure based on the B1.0 core.

The B1.0 engine is imported without starting its UI, then extended. All existing
procedural B1.0 artwork remains in luma_assets.json; c1 world/art data are merged
into a separate luma_assets_c1.json at startup. No voice dependencies added.

Deployment: put this file and sggc1_assets.py next to sggb1.0.py and the
original luma_assets.json. Run: py sggc1.0.py
Third-party dependency: only the same pygame-ce used by B1.0.
"""
from __future__ import annotations

import importlib.util
import json
import math
import random
import shutil
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE_FILE=HERE/'sggb1.0.py'
if not BASE_FILE.is_file():
    raise SystemExit('C1.0 needs the original sggb1.0.py in the same folder. B1.0 will not be changed.')

spec=importlib.util.spec_from_file_location('_sgg_b10_core',BASE_FILE)
b=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=b
spec.loader.exec_module(b)

from sggc1_assets import build_combined_assets

# The original B1.0 module retains responsibility for its UI, archive lifecycle,
# note-editor, drawing engine, and settings; no modified copy of B is necessary.
b.VERSION='C1.0'
b.VERSION_TAG='VC1.0'
b.RUNTIME_FILE='sggc1.0.py'
b.SOURCE_FILE=Path(__file__).resolve()
b.SOURCE_DIR=HERE
b.LAUNCH_DIR=HERE
b.PROJECT_DIR=HERE
b.ARCHIVE_ROOT=HERE/'archives'
b.CONFIG_PATH=HERE/'sgg.config'
b.ASSET_JSON_FILE='luma_assets_c1.json'
b.ASSET_JSON_PATH=HERE/'luma_assets_c1.json'

import pygame
b.pygame=pygame

DEFAULT_KEYS={
    'up':'w','down':'s','left':'a','right':'d',
    'use':'e','inventory':'i','drop':'space','wait':'t','eat':'f',
    'buy':'b','sell':'v','respawn':'r','hints':'?','config':'f3','screenshot':'f12','exit':'escape',
}
KEY_LABELS={
    'up':'Move up','down':'Move down','left':'Move left','right':'Move right',
    'use':'Use / Take / Talk','inventory':'Inventory','drop':'Drop carried item',
    'wait':'Wait one day','eat':'Eat soup','buy':'Buy potion','sell':'Sell item',
    'respawn':'Respawn after death','hints':'Toggle hint bar','config':'Configure keys','screenshot':'Screenshot',
    'exit':'Back / Esc'
}


def keycode(keyname):
    if keyname=='?':return pygame.K_SLASH
    try:return pygame.key.key_code(str(keyname).lower())
    except (ValueError,AttributeError):return None


def matches(event,name):
    if name=='?' and event.unicode=='?':return True
    k=keycode(name)
    return k is not None and event.key==k


class C1GameModel(b.GameModel):
    """B1's model extended with world laws, NPCs, quests, money and respawns."""
    def __init__(self,engine):
        super().__init__(engine)
        self.item_meta={o['object_id']:dict(o) for o in engine.world['objects']}
        self.c1_day=1
        self.c1_gold=0
        self.c1_permissions=set()
        self.c1_flags={'heard_kart':False,'lout_warned':False,'quest_started':False,'quest_done':False,
                       'book_read':False,'pineapple_taken':False}
        self.c1_stolen=set()
        self.c1_owned_taken=set()
        self.c1_respawn_due={}
        self.c1_npcs={n['npc_id']:dict(n,alive=True) for n in engine.world.get('npcs',[])}
        self.c1_guard=None
        self.c1_guard_target=None
        self.c1_troll_angry=False
        self.c1_soup_stacks=0
        self.c1_soup_seconds=0.0
        self.c1_soup_total=0
        self.c1_dead=None
        self.c1_launch_seconds=0.0
        self.c1_elapsed=0.0
        self.c1_naz_lines_at=0
        self.c1_selected_speech=''
        self.c1_speech_seconds=0.0
        self.c1_hint_visible=True
        self.c1_config_open=False
        self.c1_rebind=None
        self.c1_wait_banner=''
        self.c1_chest_next_day=1
        self.c1_item_counter=0
        self.c1_vault_entered=False
        self.c1_quest_log=[]
        self.c1_vendors_kart={'kart_lotta'}

    def meta(self,obj):
        return self.item_meta.get(obj.object_id,{}) if obj else {}

    def is_permitted(self,obj):
        return obj and (not obj.stealable or
                        (self.meta(obj).get('owner')=='kart_lotta' and 'kart_lotta' in self.c1_permissions))

    def is_unauthorized(self,obj):
        return bool(obj and obj.stealable and not self.is_permitted(obj))

    def c1_inventory_add(self,obj):
        if obj.object_id==self.carried_object_id:self.carried_object_id=None
        obj.in_inventory=True
        if obj.object_id not in self.inventory:self.inventory.append(obj.object_id)
        self.inventory_selected_id=obj.object_id
        self.selected_object_id=None

    def c1_make_item(self,name,kind,*,price=0,area=None,stolen=False):
        self.c1_item_counter+=1
        oid=f'c1_generated_{self.c1_item_counter}'
        sizes={'potion':(25,31),'soup':(39,26),'gold':(28,24),'herb':(28,33),'cabbage':(34,31)}
        w,h=sizes.get(kind,(30,30))
        obj=b.GameObject(oid,name,kind,area or self.current_area_id,
                         self.player_x,self.player_y,w,h,takeable=True,stealable=stolen)
        self.objects.append(obj)
        self.item_meta[oid]={'object_id':oid,'name':name,'kind':kind,'value':price,'stealable':stolen}
        if stolen:self.c1_stolen.add(oid)
        self.c1_inventory_add(obj)
        return obj

    def c1_consume(self,obj):
        if obj.object_id in self.inventory:self.inventory.remove(obj.object_id)
        if self.inventory_selected_id==obj.object_id:self.inventory_selected_id=self.inventory[0] if self.inventory else None
        obj.in_inventory=False
        obj.area_id='__consumed__'
        if self.carried_object_id==obj.object_id:self.carried_object_id=None

    def c1_have(self,predicate):
        for oid in self.inventory:
            o=self.object_by_id(oid)
            if o and predicate(o):return o
        return None

    def c1_nearest(self,x,y,reach=150):
        choices=[(math.hypot(x-o.x-o.width/2,y-o.y-o.height/2),o)
                 for o in self.live_objects()]
        choices.sort(key=lambda x:x[0])
        return choices[0][1] if choices and choices[0][0]<reach else None

    def c1_npc_at(self,point):
        for n in self.c1_npcs.values():
            if not n.get('alive',True) or n['area_id']!=self.current_area_id:continue
            rect=pygame.Rect(int(n['x']-n.get('width',55)/2),int(n['y']-n.get('height',75)/2),
                             n.get('width',55),n.get('height',75))
            if rect.collidepoint(point):return n
        return None

    def c1_nearest_npc(self,maxdist=150):
        options=[(math.hypot(self.player_x-n['x'],self.player_y-n['y']),n)
                 for n in self.c1_npcs.values() if n['area_id']==self.current_area_id and n.get('alive',True)]
        options.sort(key=lambda x:x[0])
        return options[0][1] if options and options[0][0]<maxdist else None

    def c1_say(self,message,duration=4):
        self.c1_selected_speech=message
        self.c1_speech_seconds=duration

    def c1_wait(self):
        self.c1_day+=1
        spawned=[]
        for obj in self.objects:
            meta=self.meta(obj)
            if not meta.get('respawn') or obj.object_id not in self.c1_respawn_due:continue
            if self.c1_day<self.c1_respawn_due[obj.object_id]:continue
            # Spawn an actual new unit, preserving the player's previously taken item.
            oid=obj.object_id
            original=meta
            replacement=b.GameObject(f'{oid}_day{self.c1_day}',original['name'],original['kind'],original['area_id'],
                float(original['x']),float(original['y']),int(original['width']),int(original['height']),
                takeable=True,stealable=bool(original.get('stealable',False)),on_shelf=bool(original.get('on_shelf',False)))
            self.objects.append(replacement)
            self.item_meta[replacement.object_id]=dict(original,object_id=replacement.object_id)
            spawned.append(replacement.name)
            del self.c1_respawn_due[oid]
        # Every product tagged for respawn is eligible again once its own copy is picked.
        if self.c1_dead:self.c1_dead=None
        self.c1_soup_seconds=0.0
        self.c1_soup_stacks=0
        if self.c1_day>=self.c1_chest_next_day:self.c1_wait_banner='Caravan chest restocked.'
        else:self.c1_wait_banner=''
        return f'Day {self.c1_day}. ' + (f'Restocked {len(spawned)} vegetables. ' if spawned else '')+self.c1_wait_banner

    def c1_mark_respawn(self,obj):
        days=self.meta(obj).get('respawn')
        if days:self.c1_respawn_due[obj.object_id]=self.c1_day+int(days)

    def c1_witnesses(self,obj):
        """Witnessing is independent of the item's persistent ownership."""
        return self.is_vendor_watching(obj)


class C1StateMachine(b.StateMachine):
    """Explicit player-action rules. B1 editor, screenshot and archives stay intact."""
    def __init__(self,*args,**kw):
        super().__init__(*args,**kw)
        saved=self.config.get('keybinds',{})
        self.c1_keys=dict(DEFAULT_KEYS)
        if isinstance(saved,dict):
            for action,key in saved.items():
                if action in DEFAULT_KEYS and isinstance(key,str) and keycode(key) is not None:self.c1_keys[action]=key
        self.c1_rng=random.Random()
        self._log('C1 CONFIG','Keyboard mappings: '+json.dumps(self.c1_keys))

    def start_game(self):
        super().start_game()
        if self.game:
            self._set_status('C1.0: WASD/ARROWS move; E take/use/talk; click carry/drop; F3 configure; ? hints. Explore BritRun!')
            self._log('C1 WORLD',f'{len(self.game.areas)} areas, {len(self.game.objects)} objects, {len(self.game.c1_npcs)} NPCs.')

    def _speech(self,message,seconds=4):
        game=self.game
        if game:game.c1_say(message,seconds)
        self._set_status(message)

    def _spawn_guard(self,target,source_obj):
        game=self.game
        if not game:return
        vendors=game.current_area.vendors
        if vendors:
            v=min(vendors,key=lambda v:math.hypot(v['x']-source_obj.x,v['y']-source_obj.y))
            x,y=float(v['x'])+68,float(v['y'])+72
            name=v.get('name','Vendor')
        else:
            x,y=game.player_x+90,game.player_y-60;name='Witness'
        game.c1_guard={'area_id':game.current_area_id,'x':x,'y':y,'name':'City Guard','asset':'guard',
                       'width':62,'height':90,'alive':True}
        game.c1_guard_target=target
        self._speech(f'{name}: HELP! THIEF! GUARDS!  ({target.upper()} is wanted!)',6)
        self._log('CRIME',f'Witness reported {source_obj.name}; accused={target}; area={game.current_area_id}')

    def _take(self,obj):
        g=self.game
        if not g or obj.in_inventory:return
        if not g.close_to_object(obj):
            self._speech(f'Move closer to {obj.name} first.');return
        if not obj.takeable:
            self._activate(obj);return
        watched=g.is_unauthorized(obj) and g.c1_witnesses(obj)
        if g.is_unauthorized(obj):
            g.c1_stolen.add(obj.object_id)
            g.c1_owned_taken.add(obj.object_id)
        # Direct take is permitted even when witnessed. Witnessing causes a guard!
        if obj.kind=='gold_pile':
            value=int(g.meta(obj).get('value',19000))
            g.c1_gold+=value
            obj.area_id='__consumed__';obj.in_inventory=False
            if g.carried_object_id==obj.object_id:g.carried_object_id=None
            self._speech(f'Pocketed {value:,} gold. Total: {g.c1_gold:,}.')
        else:
            g.c1_inventory_add(obj)
            self._speech(f'{"STOLEN" if g.is_unauthorized(obj) else "Took"}: {obj.name}. Inventory: {len(g.inventory)} items.')
        g.c1_mark_respawn(obj)
        self._log('C1 ITEM',f'E take: {obj.name}; unauthorized={g.is_unauthorized(obj)} witnessed={bool(watched)}')
        if watched:self._spawn_guard('player',obj)
        if obj.object_id=='purple_passion_pineapple':
            g.c1_flags['pineapple_taken']=True
            g.c1_troll_angry=True
            self._speech('FROSTY ROARS! GET OUT! (Two soups make a fast escape.)',6)

    def _activate(self,obj):
        g=self.game
        if not g:return
        meta=g.meta(obj)
        kind=obj.kind
        if kind in ('door','path','portal'):
            if not g.close_to_object(obj):self._speech('Walk closer to the entrance.');return
            trigger='door' if kind=='door' else kind
            conn=g.activate_connection(trigger,source_object_id=obj.object_id)
            if conn:self._area_enter(conn)
            else:self._speech('That doorway is not connected yet.')
            return
        action=meta.get('activity')
        if action=='locked':
            self._speech('The treasure-room gate is LOCKED. Perhaps the wall has a weakness...')
        elif action=='clip':
            held=g.object_by_id(g.carried_object_id)
            if held and held.kind=='plate' and g.close_to_object(obj,):
                conn=g.activate_connection('clip',source_object_id=obj.object_id)
                if conn:
                    g.c1_vault_entered=True
                    self._area_enter(conn)
                    self._log('EXPLOIT','Plate clipped player through the intended castle wall seam')
            else:self._speech('An odd gap in the wall. A broad, flat platter might provide some leverage...')
        elif action=='book':
            g.c1_flags['book_read']=True
            self._speech('RECIPE: Purple Passion Pineapple + Redroot + Moonflower. Alchemy table crafts the enhancement potion.',8)
        elif action=='alchemy':self._alchemy()
        elif action=='cook':self._cook()
        elif action=='chest':self._chest()
        elif action in ('armor','weapons'):self._speech('The shop facade is here, but its interior will open in a later version.')
        else:self._speech(f'{obj.name} does nothing special... yet.')

    def _area_enter(self,conn):
        g=self.game
        if not g:return
        self._log('AREA TRANSITION',f'{conn.from_area_id} -> {conn.to_area_id} via {conn.trigger}')
        self._speech(f'{conn.label}.  {g.current_area.display_name}.')
        if g.current_area_id=='giant_camp':
            self._die('GIANT SPACE PROGRAM: you have been launched into orbit!',launch=True)
        elif g.current_area_id=='mudcrab_river':
            self._die('MUDCRABS: death by an astonishingly aggressive crustacean.')
        elif g.current_area_id=='southern_wilds':
            self._die('That way lies certain doom. The wilderness wins.')

    def _die(self,reason,launch=False):
        g=self.game
        if not g or g.c1_dead:return
        g.c1_dead=reason
        g.c1_launch_seconds=1.3 if launch else 0
        g.c1_troll_angry=False
        g.c1_guard=None
        g.c1_guard_target=None
        self._speech('YOU DIED: '+reason+' Press R to respawn in BritRun Market.',10)
        self._log('PLAYER DEATH',reason)

    def _respawn(self):
        g=self.game
        if not g:return
        g.c1_dead=None
        g.c1_launch_seconds=0
        g.current_area_id='britrun_market'
        g.player_x,g.player_y=640.0,488.0
        g.carried_object_id=None
        g.c1_guard=None;g.c1_guard_target=None
        g.c1_troll_angry=False
        g.c1_soup_seconds=0.0;g.c1_soup_stacks=0
        if g.c1_flags['pineapple_taken'] and not g.c1_flags['quest_done']:
            pp=g.object_by_id('purple_passion_pineapple')
            if pp and pp.object_id in g.inventory:
                g.c1_consume(pp)
            if pp:
                pp.area_id='troll_cave';pp.x=638;pp.y=146;pp.in_inventory=False
            g.c1_flags['pineapple_taken']=False
        self._speech('Respawned in BritRun Market. Learn, adapt, and annoy Murphy.')

    def _chest(self):
        g=self.game
        if g.c1_day<g.c1_chest_next_day:
            self._speech(f'Hidden caravan chest is empty. Respawns on day {g.c1_chest_next_day}. Press T to wait.');return
        g.c1_gold+=2000
        for name,kind,price in [('Khajiit Trinket','gold',450),('Exotic Spice','herb',190),('Caravan Bauble','gold',320)]:
            g.c1_make_item(name,kind,price=price)
        g.c1_chest_next_day=g.c1_day+2
        self._speech(f'KITTY CARAVAN CHEST! +2,000 gold and 3 goods. Gold: {g.c1_gold:,}. Restocks in two days.',7)
        self._log('EXPLOIT',f'Hidden caravan chest loot; day {g.c1_day}; next {g.c1_chest_next_day}')

    def _alchemy(self):
        g=self.game
        if g.c1_flags['quest_done']:
            self._speech('The alchemy table still smells vaguely of purple pineapples.');return
        pineapple=g.c1_have(lambda o:o.kind=='pineapple')
        redroot=g.c1_have(lambda o:'redroot' in o.name.lower())
        moonflower=g.c1_have(lambda o:'moonflower' in o.name.lower())
        missing=[title for title,obj in [('Purple Passion Pineapple',pineapple),('Redroot',redroot),('Moonflower',moonflower)] if not obj]
        if missing:
            self._speech('ALCHEMY: missing '+', '.join(missing)+'. The recipe book explains why.',7);return
        for obj in (pineapple,redroot,moonflower):g.c1_consume(obj)
        g.c1_make_item('Potion of Increased Physical Enhancement','potion',price=69000)
        self._speech('SUCCESS! Crafted the Potion of Increased Physical Enhancement. Take it to Fearmonger!',7)
        self._log('CRAFT','Potion of Increased Physical Enhancement created from PPP, Redroot, Moonflower')

    def _cook(self):
        g=self.game
        tomato=g.c1_have(lambda o:o.kind=='tomato')
        cabbage=g.c1_have(lambda o:o.kind=='cabbage')
        if not tomato or not cabbage:
            self._speech('COOKPOT: a bowl of soup needs one tomato and one cabbage. Kart-lotta restocks daily.');return
        g.c1_consume(tomato);g.c1_consume(cabbage)
        g.c1_make_item('Vegetable Soup','soup',price=55)
        self._speech('Cooked Vegetable Soup! Press F to eat. Two bowls give you the speed to outrun Frosty.')
        self._log('CRAFT','Vegetable soup: tomato + cabbage')

    def _eat(self):
        g=self.game
        obj=g.c1_have(lambda o:o.kind=='soup')
        if not obj:self._speech('No vegetable soup in inventory. Use the inn cooking pot first.');return
        g.c1_consume(obj)
        g.c1_soup_stacks=min(2,g.c1_soup_stacks+1)
        g.c1_soup_seconds=max(13.0,g.c1_soup_seconds)+11.0
        speed='FULL CABBAGE POWER (470 px/s)' if g.c1_soup_stacks>=2 else 'warm legs (280 px/s)'
        self._speech(f'Ate soup. {speed}. {g.c1_soup_seconds:.0f}s remaining.')
        self._log('SOUP',f'stacks={g.c1_soup_stacks},duration={g.c1_soup_seconds:.1f}')

    def _buy(self):
        g=self.game
        if g.current_area_id!='alchemy_shop' or not g.close_to(550,231,220):
            self._speech('To buy the potion, visit the Alchemy Shopkeeper and press B.');return
        if g.c1_gold<69000:
            self._speech(f'Potion price: 69,000. You have {g.c1_gold:,} gold. Need {69000-g.c1_gold:,} more.');return
        g.c1_gold-=69000
        g.c1_make_item('Potion of Increased Physical Enhancement','potion',price=69000)
        self._speech('Bought the enhancement potion for 69,000 gold. The mage awaits!')
        self._log('TRADE',f'Bought quest potion; remaining gold {g.c1_gold}')

    def _sell(self):
        g=self.game
        if g.current_area_id!='alchemy_shop' or not g.close_to(550,231,220):
            self._speech('Press V near the Alchemy Shopkeeper to sell selected inventory goods.');return
        oid=g.inventory_selected_id
        obj=g.object_by_id(oid)
        if not obj or obj.object_id not in g.inventory:
            self._speech('Open inventory (I), click a good, and press V near the shopkeeper.');return
        if obj.kind=='potion' and 'Enhancement' in obj.name:
            self._speech('Better keep that potion for Fearmonger!');return
        val=int(g.meta(obj).get('value',g.meta(obj).get('price',65)))
        if val<=0:val={'gold':180,'herb':35,'potion':125,'plate':20,'cabbage':15,'tomato':12}.get(obj.kind,45)
        g.c1_consume(obj)
        g.c1_gold+=val
        self._speech(f'Sold {obj.name} for {val:,} gold. Purse: {g.c1_gold:,}.')
        self._log('TRADE',f'Sold {obj.name} for {val}; gold={g.c1_gold}')

    def _talk(self,n):
        g=self.game
        nid=n['npc_id']
        if nid=='naz':
            self._speech(self.c1_rng.choice(n.get('lines',['I live in the Gold District, you know.'])),5)
        elif nid=='inn_lout':
            if g.c1_flags['heard_kart'] and not g.c1_flags['lout_warned']:
                g.c1_flags['lout_warned']=True
                self._speech('You: Leave Kart-lotta alone!  Inn Lout: All right, all right! Tell her I am sorry!',7)
                self._log('QUEST','Confronted inn lout on Kart-lotta\'s behalf')
            elif g.c1_flags['lout_warned']:
                self._speech('Inn Lout: I said I would leave Kart-lotta alone!')
            else:self._speech('Inn Lout: That vegetable seller is far too good for this dump!')
        elif nid=='innkeeper':
            self._speech('Innkeeper: My cookpot is free for travelers. A tomato and a cabbage make a fine soup.')
        elif nid=='fearmonger':
            potion=g.c1_have(lambda o:'increased physical enhancement' in o.name.lower())
            if g.c1_flags['quest_done']:
                self._speech('Fearmonger: Ah, my heroic benefactor! I shall never forget your... assistance.')
            elif potion:
                g.c1_consume(potion)
                g.c1_gold+=5000
                g.c1_flags['quest_done']=True
                self._speech('MAIN QUEST COMPLETE! Fearmonger pays 5,000 gold. "My confidence has returned!"',9)
                self._log('QUEST','MAIN QUEST COMPLETE: delivered enhanced potion')
            else:
                g.c1_flags['quest_started']=True
                self._speech('Fearmonger: A delicate personal problem! Bring me a Potion of Increased Physical Enhancement. I will pay well!',9)
                self._log('QUEST','Quest accepted: acquire enhancement potion by any route')
        else:self._speech(n['name']+': Good day.')

    def _talk_vendor(self,v):
        g=self.game
        vid=v.get('vendor_id')
        if vid=='kart_lotta':
            if g.c1_flags['lout_warned'] and 'kart_lotta' not in g.c1_permissions:
                g.c1_permissions.add('kart_lotta')
                self._speech('Kart-lotta: Ohhh, my hero! Take my tomatoes and cabbages freely. They are sooooo firm!',9)
                self._log('QUEST','Kart-lotta befriended; vegetable permission granted')
            elif 'kart_lotta' in g.c1_permissions:
                self._speech(self.c1_rng.choice(['Kart-lotta: Those are the ripest cabbages in BritRun!',
                   'Kart-lotta: Anything on my stall is yours, darling!','Kart-lotta: My tomatoes are the BEST!']))
            else:
                g.c1_flags['heard_kart']=True
                self._speech(self.c1_rng.choice(['Kart-lotta: Ohhhh, my tomatoes are the best! But a lout at the inn keeps bothering me!',
                   'Kart-lotta: My cabbages are soooooo ripe and firm. If only that inn jerk would leave me alone!',
                   'Kart-lotta: Could somebody please tell that troublesome inn patron to stop pestering me?']),8)
        elif vid=='alchemy_vendor':
            self._speech(f'Alchemist: Enhancement potion? A mere 69,000 gold. Press B to buy, V to sell, E at the table to craft.')
        else:self._speech(f'{v.get("name","Vendor")}: Fresh goods and questionable prices!')

    def _use_nearest(self,ui):
        g=self.game
        point=ui.screen_to_game(pygame.mouse.get_pos())
        # A target under the cursor has highest priority, then nearest NPC/vendor/object.
        if point:
            obj=g.hit_test(point)
            if obj and (g.close_to_object(obj) or obj.kind in ('door','path','portal')):
                self._take(obj) if obj.takeable else self._activate(obj)
                return
            n=g.c1_npc_at(point)
            if n and g.close_to(n['x'],n['y'],180):self._talk(n);return
            vendor_hit=g.vendor_at(point)
            if vendor_hit:
                v=vendor_hit[0]
                if g.close_to(v['x'],v['y'],190):self._talk_vendor(v);return
        # If nothing was deliberately hovered, favor NPCs close enough to talk.
        n=g.c1_nearest_npc(105)
        if n:self._talk(n);return
        candidates=[(math.hypot(g.player_x-v['x'],g.player_y-v['y']),v)
                    for v in g.current_area.vendors]
        candidates.sort(key=lambda t:t[0])
        closest_obj=g.c1_nearest(g.player_x,g.player_y,118)
        if closest_obj:
            self._take(closest_obj) if closest_obj.takeable else self._activate(closest_obj)
            return
        if candidates and candidates[0][0]<175:
            self._talk_vendor(candidates[0][1]);return
        self._speech('Nothing close enough to activate. Move closer and point at it, then press E.')

    def _mouse_game(self,event,ui):
        g=self.game
        if ui.layout.game_back_button.collidepoint(event.pos):
            self.transition(b.AppState.MAIN,'Back to Tool button');return
        if ui.layout.game_screenshot_button.collidepoint(event.pos):ui.save_screenshot(self);return
        point=ui.screen_to_game(event.pos)
        if point is None:return
        if g.c1_config_open:
            # Rows of the keybind dialog are clickable to select a mapping.
            for i,k in enumerate(DEFAULT_KEYS):
                rect=pygame.Rect(380,94+i*29,490,27)
                if rect.collidepoint(point):g.c1_rebind=k;self._speech(f'Press any key for {KEY_LABELS[k]}...');return
            return
        if g.inventory_open:
            if g.inventory_close_rect().collidepoint(point):g.inventory_open=False;return
            if g.inventory_drop_rect().collidepoint(point):self._drop_inventory_selection(g);return
            if g.inventory_panel_rect().collidepoint(point):
                for i,oid in enumerate(g.inventory[:12]):
                    if g.inventory_row_rect(i).collidepoint(point):
                        g.inventory_selected_id=oid
                        obj=g.object_by_id(oid)
                        self._speech('Selected '+obj.name if obj else 'Missing inventory item')
                        return
                return
            g.inventory_open=False;return
        if g.inventory_button_rect().collidepoint(point):
            g.inventory_open=True
            if g.inventory_selected_id not in g.inventory:g.inventory_selected_id=g.inventory[0] if g.inventory else None
            return
        held=g.object_by_id(g.carried_object_id)
        vendor_hit=g.vendor_at(point)
        obj=g.hit_test(point)
        if held is None and vendor_hit and vendor_hit[1]=='head' and g.bucket_on_head_vendor_id==vendor_hit[0].get('vendor_id'):
            if g.close_to(vendor_hit[0]['x'],vendor_hit[0]['y'],155):
                bucket=next((o for o in g.objects if o.kind=='bucket' and o.area_id==g.current_area_id),None)
                if bucket:
                    g.carried_object_id=bucket.object_id;g.bucket_on_head_vendor_id=None
                    g.sync_carried_position()
                    self._speech('Retrieved bucket. Click near a vendor head to cover their eyes.')
            return
        if held and held.kind=='bucket' and vendor_hit and vendor_hit[1]=='head':
            v=vendor_hit[0]
            if not g.close_to(v['x'],v['y'],155):self._speech('Move closer to the vendor first.');return
            g.bucket_on_head_vendor_id=v['vendor_id'];g.carried_object_id=None
            held.area_id=g.current_area_id
            held.x=float(v['x']-held.width/2);held.y=float(v['y']-43)
            self._speech('BUCKET ON FACE! Vendor cannot witness theft while properly bucketed.')
            self._log('EXPLOIT','Bucket placed covering '+v['vendor_id'])
            return
        if held:
            if not g.close_to(*point,reach=150):self._speech('Too far away to place the carried item.');return
            x,y=point
            if vendor_hit:
                v=vendor_hit[0];x=v['x']+58;y=v['y']+47
            elif obj and obj.object_id!=held.object_id:
                x=obj.x+obj.width+held.width/2+8;y=obj.y+obj.height/2
            # Clicking the carried item, or the player, no longer transfers to inventory.
            g.place_object_at(held,x,y,on_shelf=bool(obj and obj.on_shelf))
            g.carried_object_id=None
            self._speech(f'Placed {held.name}. E takes an item into inventory; clicks only carry/place.')
            return
        if obj:
            if not g.close_to_object(obj):self._speech(f'Move closer to {obj.name}.');return
            if obj.takeable:
                if obj.object_id=='purple_passion_pineapple':
                    g.c1_troll_angry=True
                    self._speech('FROSTY ROARS! The pineapple is HIS! Dash for the exit!')
                g.carried_object_id=obj.object_id;g.selected_object_id=obj.object_id
                g.sync_carried_position()
                self._speech(f'Carrying {obj.name}. Click nearby to place it; E puts it in inventory.')
            else:
                g.selected_object_id=obj.object_id
                self._speech(f'{obj.name} selected. Press E to activate it.')
            return
        if vendor_hit:
            self._speech(vendor_hit[0].get('name','Vendor')+': press E to talk; a carried bucket can be placed on the head.')
        else:
            n=g.c1_npc_at(point)
            if n:self._speech(n['name']+': press E to talk.')
            else:g.selected_object_id=None

    def _dispatch_game(self,event,ui):
        g=self.game
        if not g:
            self.transition(b.AppState.MAIN,'Missing game model');return
        if event.type==pygame.KEYDOWN:
            if g.c1_rebind:
                action=g.c1_rebind
                if event.key!=pygame.K_ESCAPE:
                    val='?' if event.unicode=='?' else pygame.key.name(event.key)
                    self.c1_keys[action]=val
                    self.config['keybinds']=dict(self.c1_keys)
                    err=self.persist_preference('keybinds',dict(self.c1_keys))
                    self._speech(f'{KEY_LABELS[action]} is now {val.upper()}.' if not err else f'Settings save failed: {err}')
                g.c1_rebind=None;return
            if matches(event,self.c1_keys['config']):
                g.c1_config_open=not g.c1_config_open
                self._speech('Keyboard configuration: click a row then press its new key.' if g.c1_config_open else 'Configuration closed.')
                return
            if g.c1_config_open:
                if event.key==pygame.K_ESCAPE:g.c1_config_open=False
                return
            if g.c1_dead:
                if matches(event,self.c1_keys['respawn']):self._respawn()
                return
            if matches(event,self.c1_keys['exit']):
                if g.inventory_open:g.inventory_open=False
                else:
                    self.transition(b.AppState.MAIN,'Returned from Play Game')
                    self._set_status('Returned to SGG tool.')
                return
            if matches(event,self.c1_keys['screenshot']) or (event.key==pygame.K_s and (pygame.key.get_mods()&pygame.KMOD_CTRL)):
                ui.save_screenshot(self);return
            if matches(event,self.c1_keys['hints']):
                g.c1_hint_visible=not g.c1_hint_visible
                self._speech('Hints '+('ON' if g.c1_hint_visible else 'OFF'))
                return
            if matches(event,self.c1_keys['inventory']):
                g.inventory_open=not g.inventory_open
                if g.inventory_selected_id not in g.inventory:g.inventory_selected_id=g.inventory[0] if g.inventory else None
                return
            if matches(event,self.c1_keys['wait']):self._speech(g.c1_wait());return
            if matches(event,self.c1_keys['eat']):self._eat();return
            if matches(event,self.c1_keys['buy']):self._buy();return
            if matches(event,self.c1_keys['sell']):self._sell();return
            if matches(event,self.c1_keys['drop']):
                if g.carried_object_id:
                    o=g.object_by_id(g.carried_object_id)
                    if o:g.place_object_at(o,g.player_x+31,g.player_y+17)
                    g.carried_object_id=None
                    self._speech('Dropped the carried item.')
                elif g.inventory_open:self._drop_inventory_selection(g)
                return
            if matches(event,self.c1_keys['use']):
                if g.inventory_open:
                    o=g.object_by_id(g.inventory_selected_id)
                    if o and o.kind=='soup':self._eat()
                    else:self._speech('Press F to eat soup. E works on objects, doors, tables and people.')
                elif g.carried_object_id:
                    o=g.object_by_id(g.carried_object_id)
                    if o:self._take(o)
                else:self._use_nearest(ui)
                return
        if event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
            if not g.c1_dead:self._mouse_game(event,ui)

    def update(self,elapsed_seconds,ui):
        g=self.game
        if self.state is not b.AppState.PLAY_GAME or not g:return
        dt=max(0.0,min(0.05,elapsed_seconds))
        g.c1_elapsed+=dt
        if g.c1_speech_seconds>0:g.c1_speech_seconds=max(0.0,g.c1_speech_seconds-dt)
        if g.c1_soup_seconds>0:
            g.c1_soup_seconds=max(0.0,g.c1_soup_seconds-dt)
            if not g.c1_soup_seconds:g.c1_soup_stacks=0
        if g.c1_dead:
            g.c1_launch_seconds=max(0.0,g.c1_launch_seconds-dt)
            return
        if g.c1_config_open:return
        keys=pygame.key.get_pressed()
        def pressed(action):
            code=keycode(self.c1_keys[action])
            return bool(code is not None and keys[code])
        dx=int(pressed('right') or keys[pygame.K_RIGHT])-int(pressed('left') or keys[pygame.K_LEFT])
        dy=int(pressed('down') or keys[pygame.K_DOWN])-int(pressed('up') or keys[pygame.K_UP])
        if pygame.key.get_mods()&pygame.KMOD_CTRL and pressed('down'):dy=0
        if dx or dy:
            length=math.hypot(dx,dy)
            speed=470 if g.c1_soup_stacks>=2 and g.c1_soup_seconds>0 else (280 if g.c1_soup_seconds>0 else 220)
            nx=g.player_x+dx/length*speed*dt
            ny=g.player_y+dy/length*speed*dt
            if g.can_move_to(nx,g.player_y):g.player_x=nx
            if g.can_move_to(g.player_x,ny):g.player_y=ny
            g.sync_carried_position()
            edge=None
            if g.player_x<=27:edge='left'
            elif g.player_x>=b.GAME_WIDTH-27:edge='right'
            elif g.player_y<=31:edge='top'
            elif g.player_y>=b.GAME_HEIGHT-25:edge='bottom'
            if edge:
                conn=g.activate_connection('edge',edge=edge)
                if conn:self._area_enter(conn)
            # Hidden seam is passable ONLY while holding a platter and pressing toward it.
            if (g.current_area_id=='castle_hall' and not g.c1_dead and
                g.carried_object_id and (o:=g.object_by_id(g.carried_object_id)) and o.kind=='plate' and
                970<g.player_x<1070 and 210<g.player_y<405 and dx>0):
                conn=g.activate_connection('clip',source_object_id='vault_wall_seam')
                if conn:g.c1_vault_entered=True;self._area_enter(conn)
        self._npc_tick(dt)

    def _npc_tick(self,dt):
        g=self.game
        naz=g.c1_npcs.get('naz')
        if naz and naz.get('alive',True):
            # Slow wandering in the market; he notices dropped valuables near him.
            if g.current_area_id=='britrun_market':
                target=None
                for o in g.live_objects():
                    if o.kind in ('gold','gold_pile') and o.moved and not o.in_inventory and o.object_id!=g.carried_object_id:
                        if abs(o.x-naz['x'])<260:target=o;break
                if target:
                    dest=target.x+target.width/2
                    naz['x']+=max(-72*dt,min(72*dt,dest-naz['x']))
                    if abs(naz['x']-dest)<31:
                        # Naz is not the player; apply the SAME ownership and witness logic.
                        observed=g.is_vendor_watching(target) and g.is_unauthorized(target)
                        target.area_id='__consumed__'
                        naz['holding']=target.name
                        self._log('NPC ACTION',f'Naz took {target.name}; witnessed={observed}')
                        if observed:self._spawn_guard('naz',target)
                        else:g.c1_say('Naz: Finders keepers, peasants!',4)
                else:
                    naz['x']=min(1110,max(555,naz['x']+math.sin(g.c1_elapsed*.75)*35*dt))
            if g.c1_elapsed>g.c1_naz_lines_at+13 and g.current_area_id=='britrun_market':
                g.c1_naz_lines_at=g.c1_elapsed
                g.c1_say(self.c1_rng.choice(naz.get('lines',['I am important!'])),4)
        guard=g.c1_guard
        if guard and guard['area_id']==g.current_area_id:
            if g.c1_guard_target=='naz':
                target=g.c1_npcs.get('naz')
                if not target or not target.get('alive',True):g.c1_guard=None;return
                tx,ty=target['x'],target['y']
            else:tx,ty=g.player_x,g.player_y
            vx=tx-guard['x'];vy=ty-guard['y'];length=math.hypot(vx,vy)
            if length>1:
                speed=330 if g.c1_guard_target=='player' else 370
                guard['x']+=vx/length*speed*dt;guard['y']+=vy/length*speed*dt
            if length<52:
                if g.c1_guard_target=='naz':
                    g.c1_npcs['naz']['alive']=False
                    g.c1_guard=None;g.c1_guard_target=None
                    self._speech('Guard: Justice is served! Naz the Jerk has been slain for stealing!',7)
                    self._log('NPC DEATH','Naz the Jerk killed by guard for observed theft')
                else:self._die('Caught by a guard after a witnessed theft!')
        if g.current_area_id=='troll_cave' and g.c1_troll_angry:
            troll=g.c1_npcs.get('troll')
            if troll:
                vx=g.player_x-troll['x'];vy=g.player_y-troll['y'];dist=math.hypot(vx,vy)
                if dist>1:
                    speed=305
                    troll['x']+=vx/dist*speed*dt;troll['y']+=vy/dist*speed*dt
                if dist<67:self._die('Frosty the Trollman gives you a warm welcome with his claws!')


class C1Interface(b.SGGInterface):
    """Additional art/UI draw layer; the original B1.0 look remains unchanged."""
    def _draw_game_scene(self,surface,g):
        engine=self.machine.draw_engine
        if engine is None:return super()._draw_game_scene(surface,g)
        # Intercept TWO specific B1 rendering roles, without changing original art.
        draw_original=engine.draw_asset
        roles=engine.data.get('render_roles',{})
        vendor_asset=roles.get('vendor','vendor')
        bucket_asset=roles.get('bucket_on_vendor_head','bucket_inverted')
        def draw_override(dst,name,rect=None):
            # The caravan's vendor chest is intentionally invisible until hovered.
            if name=='chest' and g.current_area_id=='stables' and rect is not None and rect.x>1100:
                return None
            if name==vendor_asset and rect is not None:
                for v in g.current_area.vendors:
                    if v.get('recipe') and abs(rect.centerx-v['x'])<4 and abs(rect.centery-v['y'])<4:
                        name=v['recipe'];break
            if name==bucket_asset and rect is not None and g.bucket_on_head_vendor_id:
                v=g.vendor_by_id(g.bucket_on_head_vendor_id)
                if v and any(z.get('vendor_id')==g.bucket_on_head_vendor_id for z in g.current_area.vendors):
                    rect=pygame.Rect(int(v['x']-31),int(v['y']-44),62,47)
            return draw_original(dst,name,rect)
        engine.draw_asset=draw_override
        try:super()._draw_game_scene(surface,g)
        finally:engine.draw_asset=draw_original
        # Additional characters retain the procedural recipe style.
        for npc in g.c1_npcs.values():
            if npc['area_id']!=g.current_area_id or not npc.get('alive',True):continue
            r=pygame.Rect(round(npc['x']-npc.get('width',60)/2),round(npc['y']-npc.get('height',80)/2),
                          npc.get('width',60),npc.get('height',80))
            engine.draw_asset(surface,npc['asset'],r)
        if g.c1_guard and g.c1_guard['area_id']==g.current_area_id:
            guard=g.c1_guard
            r=pygame.Rect(round(guard['x']-31),round(guard['y']-45),62,90)
            engine.draw_asset(surface,'guard',r)
        # Replace the B1 status headline with the C1 interaction and currency HUD.
        pygame.draw.rect(surface,(20,18,22),(0,0,b.GAME_WIDTH,44))
        pygame.draw.line(surface,(187,145,83),(0,43),(b.GAME_WIDTH,43),2)
        self._c1_text(surface,g.current_area.display_name.upper(),20,12,(255,224,168),self.game_font,325)
        self._c1_text(surface,f'DAY {g.c1_day}  •  GOLD {g.c1_gold:,}',420,12,(247,226,171),self.game_small_font,285)
        self._c1_text(surface,'E USE  ·  CLICK CARRY  ·  F3 KEYS',710,12,(236,232,221),self.game_small_font,350)
        if g.c1_flags['quest_done']:
            self._c1_text(surface,'QUEST COMPLETE',990,56,(127,255,165),self.game_font,268)
        elif g.c1_flags['quest_started']:
            self._c1_text(surface,'FIND ENHANCEMENT POTION',1013,57,(249,220,147),self.game_small_font,253)
        if g.c1_soup_seconds>0:
            self._c1_text(surface,f'SOUP x{g.c1_soup_stacks} {g.c1_soup_seconds:.0f}s',25,52,
                          (156,255,157),self.game_small_font,260)
        # The hint/status bar can be turned entirely off with '?' (no decorative empty panel).
        hint_rect=pygame.Rect(16,574,1248,31)
        if not g.c1_hint_visible:
            # Restore the original background pixels for the bottom of this canvas.
            # No animated character is stationed down here.
            bg=pygame.Surface((b.GAME_WIDTH,b.GAME_HEIGHT))
            engine.draw_asset(bg,g.current_area.background_asset,pygame.Rect(0,0,b.GAME_WIDTH,b.GAME_HEIGHT))
            surface.blit(bg,hint_rect,hint_rect)
        else:
            pygame.draw.rect(surface,(18,16,17),hint_rect,border_radius=5)
            pygame.draw.rect(surface,(174,131,74),hint_rect,1,border_radius=5)
            hint='E=TAKE/USE/TALK  CLICK=CARRY/PLACE  F=SOUP  T=WAIT  B=BUY  V=SELL  ?=HIDE  F3=KEYS'
            if g.current_area_id=='castle_hall':hint='TREASURE ROOM: the locked gate is not the only way in. A platter + a suspicious wall seam...'
            elif g.current_area_id=='troll_cave':hint='PURPLE PASSION PINEAPPLE! Frosty attacks when you take it. Two bowls of soup = dash!'
            elif g.current_area_id=='stables':hint=f'KITTY CARAVAN: hidden chest 2,000 gold, respawns in two days. Day {g.c1_day}.'
            elif g.current_area_id=='alchemy_shop':hint='ALCHEMIST: B=buy enhancement potion (69,000g); V=sell; E=alchemy table or recipe book.'
            elif g.current_area_id=='inn_interior':hint='INN: E to confront the rude patron or cook soup; serving platter may have OTHER uses.'
            elif g.current_area_id=='mages_lab':hint='E to talk to Fearmonger and deliver his VERY PERSONAL enhancement potion.'
            self._c1_text(surface,hint,28,583,(247,240,222),self.game_small_font,1208)
        # World affordances: ownership is a separate flag from being witnessed.
        point=self.screen_to_game(pygame.mouse.get_pos()) if getattr(self,'game_blit_rect',None) else None
        if point is not None and not g.c1_config_open and not g.inventory_open:
            obj=g.hit_test(point)
            npc=g.c1_npc_at(point)
            v=g.vendor_at(point)
            if obj:
                if obj.kind in ('door','path','portal'): label=f'E: {obj.name}';color=(156,226,255)
                elif not obj.takeable:label=f'E: {obj.name}';color=(156,226,255)
                elif g.is_unauthorized(obj):
                    label=f'OWNED / STEAL: {obj.name} (E to take)';color=(255,104,104)
                else:label=f'FREE / PERMITTED: {obj.name} (E to take)';color=(148,251,173)
            elif npc:label=f'E: TALK TO {npc["name"]}';color=(238,228,185)
            elif v:label=f'E: TALK TO {v[0]["name"]}';color=(238,228,185)
            else:label=None;color=(247,240,222)
            if label:
                font=self.game_small_font
                txt=font.render(label,True,color)
                px=min(b.GAME_WIDTH-txt.get_width()-12,max(8,point[0]+15))
                py=min(b.GAME_HEIGHT-64,max(50,point[1]+13))
                rr=pygame.Rect(px-6,py-4,txt.get_width()+12,txt.get_height()+8)
                pygame.draw.rect(surface,(17,14,15),rr,border_radius=4)
                pygame.draw.rect(surface,color,rr,1,border_radius=4)
                surface.blit(txt,(px,py))
        if g.c1_speech_seconds>0 and g.c1_selected_speech:
            rr=pygame.Rect(145,506,987,58)
            pygame.draw.rect(surface,(24,22,31),rr,border_radius=8)
            pygame.draw.rect(surface,(206,164,93),rr,2,border_radius=8)
            self._c1_wrapped(surface,g.c1_selected_speech,rr.x+15,rr.y+8,rr.width-30,(253,235,195))
        if g.c1_dead:
            pygame.draw.rect(surface,(0,0,0,190),(0,0,b.GAME_WIDTH,b.GAME_HEIGHT))
            self._c1_text(surface,'YOU DIED',414,170,(246,88,80),self.game_font,460)
            self._c1_wrapped(surface,g.c1_dead,363,246,585,(255,226,205))
            self._c1_text(surface,'PRESS R TO RESPAWN',397,362,(255,226,160),self.game_font,510)
        if g.c1_config_open:self._c1_config_dialog(surface,g)

    def _c1_text(self,surface,s,x,y,color,font,width):
        txt=str(s)
        while txt and font.size(txt)[0]>width:txt=txt[:-2]+'…'
        surface.blit(font.render(txt,True,color),(x,y))

    def _c1_wrapped(self,surface,s,x,y,w,color):
        words=str(s).split();line='';lines=[]
        for word in words:
            candidate=(line+' '+word).strip()
            if self.game_small_font.size(candidate)[0]>w and line:
                lines.append(line);line=word
            else:line=candidate
        if line:lines.append(line)
        for i,line in enumerate(lines[:3]):
            surface.blit(self.game_small_font.render(line,True,color),(x,y+i*19))

    def _c1_config_dialog(self,surface,g):
        rr=pygame.Rect(355,58,570,537)
        pygame.draw.rect(surface,(25,22,29),rr,border_radius=10)
        pygame.draw.rect(surface,(214,169,101),rr,3,border_radius=10)
        self._c1_text(surface,f'CONFIGURE CONTROLS   [{self.machine.c1_keys["config"].upper()} closes]',390,65,(255,230,176),self.game_font,525)
        for i,action in enumerate(DEFAULT_KEYS):
            row=pygame.Rect(380,94+i*29,490,27)
            bg=(107,73,69) if g.c1_rebind==action else ((51,47,58) if i%2==0 else (42,37,47))
            pygame.draw.rect(surface,bg,row,border_radius=3)
            self._c1_text(surface,KEY_LABELS[action],390,row.y+4,(239,229,202),self.game_small_font,310)
            self._c1_text(surface,self.machine.c1_keys[action].upper(),772,row.y+4,(145,244,169),self.game_small_font,92)
        self._c1_text(surface,'Click a row, then press the replacement key. Esc cancels.',383,544,(222,213,192),self.game_small_font,517)


def _c1_archiver():
    archive=_original_archive()
    try:
        shutil.copy2(BASE_FILE,archive.directory/'sggb1.0.py')
        shutil.copy2(HERE/'sggc1_assets.py',archive.directory/'sggc1_assets.py')
        shutil.copy2(HERE/'c1_additions.json',archive.directory/'c1_additions.json')
        b.append_log(archive,'C1 ARCHIVE','Copied B1.0 core + C1 art builder + overlay; archived C1 source & merged recipes.')
    except Exception as exc:
        b.append_log(archive,'C1 ARCHIVE ERROR',str(exc))
        raise
    return archive


# Late-binding substitution affects only C1 execution, not the archived B1 source.
b.GameModel=C1GameModel
b.StateMachine=C1StateMachine
b.SGGInterface=C1Interface
_original_archive=b.initialize_archive
b.initialize_archive=_c1_archiver


def main():
    try:
        build_combined_assets(HERE)
    except Exception as exc:
        print(f'ERROR constructing C1 artwork: {exc}',file=sys.stderr)
        return 1
    return b.main()


if __name__=='__main__':
    raise SystemExit(main())
