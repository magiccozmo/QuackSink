"""SGG C1.0 procedural art and world-data extension for the B1.0 Luma Draw Engine.

Only Python's standard library is used. The original B1.0 recipes are retained.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def R(x,y,w,h,color,border=0):return {'op':'rect','rect':[x,y,w,h],'color':list(color),'border':border}
def P(points,color):return {'op':'polygon','points':[list(p) for p in points],'color':list(color)}
def L(x1,y1,x2,y2,color,width=2):return {'op':'line','points':[[x1,y1],[x2,y2]],'color':list(color),'width':width}
def C(x,y,r,color):return {'op':'circle','center':[x,y],'radius':r,'color':list(color)}
def E(x,y,w,h,color):return {'op':'ellipse','rect':[x,y,w,h],'color':list(color)}
def asset(w,h,commands):return {'width':w,'height':h,'commands':commands}

STONE=(112,115,105); ROAD=(132,120,98); WOOD=(101,64,37); GOLD=(225,187,93)

def building(x,y,w,h,kind='house'):
    a=[R(x,y,w,h,(115,93,70)), R(x+8,y+10,w-16,h-10,(151,121,84)),
       P([(x-18,y+5),(x+w//2,y-56),(x+w+18,y+5)],(94,59,49)),
       L(x,y+5,x+w,y+5,(212,161,96),4),R(x+w//2-23,y+h-80,46,80,(71,48,38)),
       R(x+w//2-15,y+h-75,30,75,(121,75,44)),C(x+w//2+9,y+h-34,3,GOLD)]
    if kind=='inn':
        a.extend([R(x+25,y+35,60,51,(74,60,54)),R(x+30,y+40,50,41,(236,175,91)),
                  L(x+55,y+40,x+55,y+81,(93,64,40),5),
                  R(x+w-100,y+18,80,25,(54,39,30)),R(x+w-97,y+20,74,20,(199,159,87))])
    else:
        for px in (x+37,x+w-67):
            a.extend([R(px,y+35,33,46,(59,48,45)),R(px+3,y+38,27,40,(172,190,174)),L(px+16,y+35,px+16,y+81,(96,71,53),3)])
    return a

def fantasy_background(name):
    outdoor=name not in ('inn_interior','castle_hall','mages_lab','castle_vault','troll_cave')
    if outdoor:
        sky=(83,115,127) if name not in ('giant_camp','mudcrab_river','southern_wilds') else (71,89,93)
        a=[R(0,0,1280,640,sky),R(0,320,1280,320,(84,110,78)),
           P([(0,372),(210,270),(420,365),(630,266),(810,355),(1060,268),(1280,377),(1280,477),(0,477)],(104,115,100)),
           R(0,425,1280,215,(120,118,95)),P([(525,640),(585,391),(690,391),(765,640)],ROAD),
           L(0,519,1280,519,(141,125,97),3)]
        for i in range(10):
            x=(i*147+52)%1280; y=403+(i*37)%174
            a.extend([L(x,y,x+6,y-21,(57,86,48),2), C(x+8,y-22,3,(145,154,74))])
    else:
        a=[R(0,0,1280,640,(60,44,36)),R(0,45,1280,355,(115,78,53)),R(0,393,1280,247,(109,79,54)),
           L(0,400,1280,400,(52,39,33),8)]
        for y in range(423,640,43):a.append(L(0,y,1280,y,(79,55,39),3))
        for x in range(30,1280,180):
            a.extend([R(x,44,13,355,(67,49,38)),L(x+13,65,x+179,65,(148,104,65),4)])
    if name in ('inn_outside','gold_district','castle_path','castle_exterior','front_gate'):
        if name=='inn_outside':
            a+=building(430,130,440,315,'inn')
        elif name=='gold_district':
            a+=building(90,151,310,305)+building(870,149,310,305)
        elif name=='castle_path':
            a+=building(430,180,410,240)
        elif name=='castle_exterior':
            a+=[R(207,177,868,300,(118,117,112)),R(238,195,804,272,(156,151,137)),
                R(225,120,165,342,(133,130,125)),R(888,120,165,342,(133,130,125)),
                P([(205,120),(307,40),(405,120)],(91,72,67)),P([(865,120),(969,40),(1074,120)],(91,72,67)),
                R(549,270,173,198,(68,46,42)),R(560,278,151,188,(126,82,48))]
        else:
            a+=[R(110,105,215,380,(112,107,95)),R(954,105,215,380,(112,107,95)),
                P([(95,105),(217,25),(340,105)],(85,68,58)),P([(939,105),(1062,25),(1185,105)],(85,68,58)),
                R(325,180,628,259,(126,124,109)),R(555,280,170,160,(76,57,43))]
    if name=='outside_gate':
        a+=[R(120,325,230,80,(93,98,83)),R(910,325,230,80,(93,98,83)),
             P([(500,640),(580,400),(700,400),(780,640)],(150,132,99))]
    if name=='stables':
        a+=building(65,190,340,235)
        a += [R(760,263,410,140,(108,76,47)),P([(740,263),(950,152),(1190,263)],(91,54,43)),
              R(825,327,77,95,(57,45,34)), R(987,327,77,95,(57,45,34))]
    if name=='plains':
        for x in (90,340,950,1160):
            a.extend([R(x,293,12,142,(75,63,42)),C(x+5,285,47,(53,82,54)),C(x+29,321,31,(64,91,57))])
    if name=='giant_camp':
        a.extend([P([(555,385),(697,130),(833,385)],(95,71,56)),L(695,137,695,428,(171,139,101),6),
                  C(914,431,41,(195,97,43)),C(914,431,22,(245,153,58))])
    if name=='mudcrab_river':
        a.extend([P([(340,245),(885,245),(1030,640),(225,640)],(60,114,137)),
                  L(404,284,840,284,(125,175,179),7),L(290,520,970,520,(115,168,170),5)])
    if name=='southern_wilds':
        for x in range(80,1220,165):a += [R(x,322,15,200,(57,51,43)),C(x+10,327,60,(58,71,54))]
    if name in ('mountain_path','peak'):
        a+=[P([(0,530),(245,96),(520,530)],(108,115,115)),
            P([(370,537),(680,42),(1020,537)],(129,130,129)),
            P([(800,537),(1110,121),(1280,510)],(103,116,115)),
            P([(588,186),(678,43),(771,185)],(226,226,218)),
            P([(1016,244),(1112,121),(1180,250)],(217,220,218))]
        if name=='peak':a.extend([R(567,272,154,171,(49,53,56)),P([(550,277),(641,195),(736,277)],(82,86,84))])
    if name=='troll_cave':
        a=[R(0,0,1280,640,(33,46,53)),R(0,370,1280,270,(61,77,78)),
           P([(0,0),(290,0),(210,265),(145,345),(0,450)],(81,95,104)),
           P([(1280,0),(970,0),(1070,265),(1152,345),(1280,450)],(79,94,104)),
           P([(0,0),(1280,0),(1130,120),(460,140)],(101,110,114)),
           P([(220,640),(380,360),(910,360),(1090,640)],(98,111,109))]
        for x in range(30,1250,150):a.append(P([(x,0),(x+29,0),(x+14,56+(x%55))],(130,151,154)))
    if name in ('inn_interior','castle_hall','mages_lab','castle_vault'):
        if name=='inn_interior':
            a += [R(135,210,375,105,(88,56,35)),R(150,213,345,25,(158,102,49)),
                  R(765,260,365,92,(91,64,40)),R(772,264,351,22,(166,112,65))]
            for x in range(175,500,72):a.extend([R(x,170,25,40,(146,112,76)),R(x+5,165,15,9,(197,161,93))])
        if name=='castle_hall':
            a += [R(1040,70,35,470,(84,82,83)), R(1053,190,15,169,(121,123,122)),
                  R(936,110,94,120,(81,62,53)),R(950,128,66,88,(165,131,76)),
                  R(220,120,150,270,(75,49,40)),R(240,145,110,235,(122,78,51))]
        if name=='mages_lab':
            a += [R(145,265,360,70,(63,49,40)),R(145,272,355,30,(145,94,52)),
                  R(754,215,286,108,(55,48,53)),R(760,223,273,95,(106,72,90)),
                  C(900,240,47,(107,65,134)),C(900,240,23,(173,104,179))]
        if name=='castle_vault':
            for x in range(100,1170,170):
                a.extend([R(x,380,138,92,(98,70,39)),R(x+10,385,118,25,(187,132,57)),
                          C(x+60,360,20,(222,176,65)),C(x+97,362,15,(229,175,57))])
    return asset(1280,640,a)


def sprite_assets():
    sprites={}
    sprites['female_vendor']=asset(64,88,[E(10,77,44,9,(37,33,30)),R(15,65,13,18,(67,49,42)),R(37,65,13,18,(67,49,42)),
      P([(15,36),(27,30),(43,30),(54,42),(58,75),(8,75)],(109,55,79)),P([(16,36),(43,35),(55,73),(12,73)],(163,80,113)),
      R(6,43,11,27,(194,147,105)),R(49,43,11,27,(194,147,105)),C(33,20,18,(202,157,112)),
      E(14,2,40,25,(78,50,33)),E(18,5,31,12,(102,62,43)),C(26,22,2,(42,36,31)),C(41,22,2,(42,36,31)),
      L(27,30,39,30,(129,49,54),2),R(27,36,14,6,(229,180,130))])
    sprites['naz']=asset(64,88,[E(9,77,47,9,(33,31,30)),R(14,69,15,13,(42,34,38)),R(37,69,15,13,(42,34,38)),
      P([(10,34),(54,34),(61,72),(5,72)],(133,83,51)),R(23,35,17,35,(175,135,75)),
      C(32,20,18,(202,149,109)),R(14,2,37,10,(76,56,36)),R(17,7,31,9,(115,83,47)),
      L(23,24,27,22,(46,38,33),2),L(37,22,43,24,(46,38,33),2),L(28,32,43,30,(106,56,48),2)])
    sprites['mage']=asset(64,88,[E(7,77,49,9,(33,31,32)),P([(32,0),(9,71),(54,71)],(92,62,112)),
      P([(14,24),(50,24),(57,74),(8,74)],(106,75,138)),C(32,22,15,(193,160,122)),
      R(17,27,30,14,(206,196,192)),C(26,20,2,(65,54,51)),C(39,20,2,(65,54,51)),
      L(53,28,61,83,(151,112,61),4),C(53,27,6,(167,87,184))])
    sprites['guard']=asset(64,88,[E(8,78,48,8,(33,33,35)),R(14,64,15,18,(59,62,66)),R(37,64,15,18,(59,62,66)),
      R(11,33,43,43,(94,105,118)),R(15,37,34,30,(146,152,156)),C(32,19,16,(172,141,114)),
      R(17,5,30,9,(106,116,128)),P([(11,10),(54,10),(47,22),(17,22)],(97,107,119)),
      L(52,36,60,78,(170,178,184),5)])
    sprites['lout']=asset(64,88,[E(7,77,50,9,(36,29,24)),R(13,64,14,18,(67,47,34)),R(38,64,14,18,(67,47,34)),
      P([(9,34),(52,34),(57,74),(9,74)],(93,69,44)),C(32,20,17,(178,132,101)),
      R(16,6,34,9,(69,47,32)),C(25,24,2,(38,34,31)),C(40,24,2,(38,34,31)),
      L(24,32,39,34,(111,60,57),2)])
    sprites['troll']=asset(108,143,[E(9,124,90,14,(25,34,36)),P([(18,43),(88,43),(106,130),(1,130)],(88,109,123)),
      C(53,39,34,(113,136,151)),C(36,38,5,(216,205,81)),C(71,38,5,(216,205,81)),
      R(40,64,30,7,(45,59,65)),R(17,110,25,25,(72,82,90)),R(71,110,25,25,(72,82,90))])
    sprites['giant']=asset(122,196,[E(7,177,104,17,(45,42,36)),R(16,115,34,66,(94,77,55)),R(70,115,34,66,(94,77,55)),
      P([(17,47),(104,47),(109,138),(9,138)],(165,130,89)),C(60,34,31,(192,154,120)),
      R(88,61,12,140,(111,88,62)),L(104,49,119,193,(89,61,41),11)])
    sprites['mudcrab']=asset(55,40,[E(6,15,43,19,(123,70,55)),C(15,14,8,(157,92,64)),C(41,14,8,(157,92,64)),
      C(19,13,3,(221,184,102)),C(36,13,3,(221,184,102)),
      L(6,24,0,32,(123,70,55),3),L(49,24,55,32,(123,70,55),3)])
    sprites['pineapple']=asset(38,58,[E(3,17,32,38,(116,57,156)),P([(9,15),(2,1),(18,9),(23,0),(25,12),(37,7),(29,21)],(80,140,65)),
      L(6,29,31,46,(199,136,206),3),L(7,45,32,29,(197,133,207),3),L(9,54,30,21,(145,87,162),2)])
    sprites['cabbage']=asset(34,31,[C(17,16,15,(67,112,54)),E(6,5,25,23,(108,149,77)),L(17,2,17,29,(59,104,54),3),
      L(3,15,29,15,(68,111,49),2)])
    sprites['soup']=asset(39,26,[E(2,7,35,18,(72,53,45)),E(4,5,31,12,(151,139,86)),E(7,7,25,8,(169,122,61)),
      C(15,12,2,(100,147,69)),C(26,11,2,(177,83,64))])
    sprites['plate']=asset(45,24,[E(2,7,41,15,(45,48,51)),E(5,4,35,14,(145,144,138)),E(11,8,23,7,(205,203,183))])
    sprites['chest']=asset(77,55,[R(3,18,71,34,(84,54,32)),R(5,22,67,27,(124,81,44)),
      P([(4,20),(13,5),(62,5),(74,20)],(148,98,54)),R(32,24,13,19,(208,171,69)),C(38,34,4,(75,55,38))])
    sprites['locked_door']=asset(85,120,[R(0,0,85,120,(55,55,58)),R(6,6,73,108,(107,89,76)),
      R(11,12,63,99,(55,46,43)),R(37,45,15,22,(198,154,66))])
    sprites['alchemy_table']=asset(145,85,[R(8,32,130,14,(97,61,39)),R(14,47,10,35,(81,54,38)),R(122,47,10,35,(81,54,38)),
      C(75,25,24,(126,94,125)),C(75,25,15,(189,103,151)),R(36,6,12,26,(79,88,95)),R(99,3,13,29,(85,124,110))])
    sprites['cookpot']=asset(104,67,[E(6,18,92,30,(40,41,43)),E(12,8,80,27,(111,114,118)),E(17,13,70,21,(143,111,73)),
      R(26,40,8,23,(66,59,49)),R(73,40,8,23,(66,59,49)),C(40,20,5,(103,141,75))])
    sprites['book']=asset(45,33,[R(3,4,40,26,(96,64,43)),R(5,4,17,25,(210,182,126)),R(23,4,17,25,(224,198,143)),L(22,3,22,30,(93,68,44),2)])
    sprites['gold_pile']=asset(83,51,[E(5,24,73,24,(152,105,38)),E(11,19,65,22,(225,173,65)),
      C(24,20,12,(236,199,91)),C(48,16,15,(219,176,62)),C(64,28,12,(235,190,69))])
    sprites['wall_seam']=asset(36,150,[R(13,0,19,150,(94,93,89)),L(14,0,14,150,(40,40,38),5),L(18,0,18,150,(147,138,127),2)])
    sprites['sign']=asset(120,52,[R(2,9,116,33,(71,45,32)),R(7,13,106,25,(173,128,74)),
      L(29,1,29,15,(87,62,40),3),L(91,1,91,15,(87,62,40),3)])
    return sprites


def A(name,bg,vendors=None,solid=None,sight=None,conceal=None):
    return {'area_id':name,'display_name':name.replace('_',' ').title(), 'background_asset':bg,
            'vendors':vendors or [],'solid_rects':solid or [],'sight_blockers':sight or [],'conceal_zones':conceal or []}

def O(oid,name,kind,area,x,y,w=35,h=35,**kw):
    o={'object_id':oid,'name':name,'kind':kind,'area_id':area,'x':x,'y':y,'width':w,'height':h,
       'takeable':kw.pop('takeable', True),'stealable':kw.pop('stealable',False),'on_shelf':kw.pop('on_shelf',False)}
    o.update(kw);return o

def D(a,b,source,reverse_source,where=(640,490),backwhere=(640,490)):
    """Bidirectional door pair using explicit interactive door objects."""
    return [dict(connection_id=f'{a}_to_{b}',from_area_id=a,to_area_id=b,trigger='door',source_object_id=source,
                 arrival_x=where[0],arrival_y=where[1],label=f'Enter {b.replace("_"," ").title()}'),
            dict(connection_id=f'{b}_to_{a}',from_area_id=b,to_area_id=a,trigger='door',source_object_id=reverse_source,
                 arrival_x=backwhere[0],arrival_y=backwhere[1],label=f'Return to {a.replace("_"," ").title()}')]

def X(a,b,edge,spawn,backspawn):
    other={'left':'right','right':'left','top':'bottom','bottom':'top'}[edge]
    return [dict(connection_id=f'{a}_{edge}_{b}',from_area_id=a,to_area_id=b,trigger='edge',edge=edge,arrival_x=spawn[0],arrival_y=spawn[1],label=f'Enter {b}'),
            dict(connection_id=f'{b}_{other}_{a}',from_area_id=b,to_area_id=a,trigger='edge',edge=other,arrival_x=backspawn[0],arrival_y=backspawn[1],label=f'Return to {a}')]


def build_overlay(base):
    """Generate an overlay preserving B1 art; world uses B1 market & shop."""
    assets=sprite_assets()
    outdoors=['inn_outside','front_gate','outside_gate','stables','plains','giant_camp','mudcrab_river','southern_wilds',
              'mountain_path','peak','gold_district','castle_path','castle_exterior']
    indoors=['inn_interior','castle_hall','mages_lab','castle_vault','troll_cave']
    for name in outdoors+indoors: assets[f'c1_bg_{name}']=fantasy_background(name)
    world=json.loads(json.dumps(base['world']))
    market='britrun_market'; shop='alchemy_shop'
    # Keep the B1 art, layout and old objects/doors, with one vendor changed.
    world['areas'][0]['vendors'][0]['name']='Kart-lotta'
    world['areas'][0]['vendors'][0]['vendor_id']='kart_lotta'
    world['areas'][0]['vendors'][0]['recipe']='female_vendor'
    world['areas'][0]['display_name']='BritRun Market'
    # B1 had solid side walls; C1 opens those edges to the inn and Gold District.
    world['areas'][0]['solid_rects']=[r for r in world['areas'][0].get('solid_rects',[])
                                  if not (r[0]<=40 and r[2]<=15) and not (r[0]>=1230 and r[2]<=15)]
    extra_areas=[A(n,f'c1_bg_{n}') for n in outdoors+indoors]
    world['areas'].extend(extra_areas)
    # The castle wall is solid; only the explicitly modeled platter seam bypasses it.
    for ar in extra_areas:
        if ar['area_id']=='castle_hall':
            ar['solid_rects']=[[1025,75,34,473]]
            ar['sight_blockers']=[[1025,75,34,473]]
    objects=world['objects']; cons=world['connections']
    # Existing shop connection preserved. New door + edge crossings are all explicit.
    objects.extend([
      O('market_cabbage_1','Kart-lotta Cabbage','cabbage',market,168,247,32,30,stealable=True,respawn=1,owner='kart_lotta'),
      O('market_cabbage_2','Kart-lotta Cabbage','cabbage',market,196,247,32,30,stealable=True,respawn=1,owner='kart_lotta'),
      O('market_tomato_2','Kart-lotta Tomato','tomato',market,238,247,29,29,stealable=True,respawn=1,owner='kart_lotta'),
      O('inn_front_door','The Tipsy Turnip Inn Door','door','inn_outside',589,325,91,118,takeable=False),
      O('inn_exit','Inn Exit','door','inn_interior',585,504,99,87,takeable=False),
      O('inn_cookpot','Inn Cooking Pot','cookpot','inn_interior',283,309,102,69,takeable=False,activity='cook'),
      O('castle_hall_door','Castle Hall Door','door','castle_exterior',589,325,97,115,takeable=False),
      O('castle_exit','Castle Exit','door','castle_hall',601,516,88,73,takeable=False),
      O('lab_door','Mages Lab Door','door','castle_hall',246,263,100,125,takeable=False),
      O('lab_exit','Lab Exit','door','mages_lab',596,512,87,76,takeable=False),
      O('vault_locked_door','LOCKED Treasure Room Gate','locked_door','castle_hall',945,266,77,113,takeable=False,activity='locked'),
      O('vault_wall_seam','Suspicious Wall Seam','wall_seam','castle_hall',1040,217,34,146,takeable=False,activity='clip'),
      O('vault_exit','Vault Exit','door','castle_vault',596,512,87,76,takeable=False),
      O('vault_gold_1','Castle Treasure','gold_pile','castle_vault',250,374,80,49,value=19000),
      O('vault_gold_2','Castle Treasure','gold_pile','castle_vault',524,368,80,49,value=19000),
      O('vault_gold_3','Castle Treasure','gold_pile','castle_vault',819,363,80,49,value=19000),
      O('vault_gold_4','Castle Treasure','gold_pile','castle_vault',1005,377,80,49,value=19000),
      O('inn_plate','Wooden Serving Platter','plate','inn_interior',835,288,48,26),
      O('shop_alchemy_table','Alchemy Table','alchemy_table',shop,734,347,132,87,takeable=False,activity='alchemy'),
      O('shop_recipe_book','The Potent Problem (Recipe)','book',shop,134,169,49,34,takeable=False,activity='book'),
      O('lab_recipe_book',"A Gentleman's Restorative",'book','mages_lab',389,278,49,34,takeable=False,activity='book'),
      O('shop_redroot','Redroot Herb','herb',shop,319,118,26,32,stealable=True,price=40),
      O('shop_miracle_potion','Potion of Increased Physical Enhancement','potion','alchemy_shop',553,103,26,31,
        stealable=True,owner='alchemy_vendor',price=69000,product='quest_potion'),
      O('stable_caravan_chest','Kitty Caravan Hidden Chest','chest','stables',1172,409,65,50,takeable=False,activity='chest'),
      O('troll_cave_entrance','Frost Cave Entrance','door','peak',592,285,90,115,takeable=False),
      O('troll_cave_exit','Frost Cave Exit','door','troll_cave',598,516,84,79,takeable=False),
      O('purple_passion_pineapple','Purple Passion Pineapple','pineapple','troll_cave',638,146,42,62),
      O('mountain_herb','Mountain Moonflower','herb','mountain_path',242,451,28,33),
      O('outside_wild_herb','Wild Redroot','herb','plains',880,465,28,33),
      O('market_souvenir_jar','Odd Souvenir','potion_blue',market,1059,244,24,31,stealable=True),
      O('city_gate_door','BritRun City Gate','door','front_gate',597,318,90,122,takeable=False),
      O('city_gate_return','City Gate to BritRun','door','outside_gate',597,248,90,122,takeable=False),
      O('gate_armor_sign','Armorer Sign','sign','front_gate',143,313,112,49,takeable=False,activity='armor'),
      O('gate_weapon_sign','Weapons Sign','sign','front_gate',958,313,112,49,takeable=False,activity='weapons'),
    ])
    cons.extend(D('front_gate','outside_gate','city_gate_door','city_gate_return',where=(640,450),backwhere=(640,490)))
    cons.extend(D('inn_outside','inn_interior','inn_front_door','inn_exit',where=(635,490),backwhere=(631,482)))
    cons.extend(D('castle_exterior','castle_hall','castle_hall_door','castle_exit'))
    cons.extend(D('castle_hall','mages_lab','lab_door','lab_exit'))
    cons.extend(D('peak','troll_cave','troll_cave_entrance','troll_cave_exit',where=(640,506),backwhere=(640,406)))
    cons.extend([
      dict(connection_id='castle_hall_to_vault_clip',from_area_id='castle_hall',to_area_id='castle_vault',trigger='clip',source_object_id='vault_wall_seam',arrival_x=640,arrival_y=460,label='Clipped into treasure room'),
      dict(connection_id='vault_to_hall',from_area_id='castle_vault',to_area_id='castle_hall',trigger='door',source_object_id='vault_exit',arrival_x=935,arrival_y=410,label='Back to castle hall')])
    cons.extend(X(market,'inn_outside','right',(60,490),(1205,490)))
    cons.extend(X(market,'front_gate','bottom',(640,115),(640,520)))
    cons.extend(X(market,'gold_district','left',(1210,500),(65,485)))
    cons.extend(X('gold_district','castle_path','top',(640,510),(640,100)))
    cons.extend(X('gold_district','front_gate','right',(67,440),(1220,440)))
    cons.extend(X('castle_path','castle_exterior','top',(640,510),(640,115)))
    cons.extend(X('outside_gate','stables','bottom',(640,120),(640,520)))
    cons.extend(X('stables','plains','right',(62,488),(1215,480)))
    cons.extend(X('plains','giant_camp','top',(640,500),(640,100)))
    cons.extend(X('plains','mudcrab_river','right',(65,475),(1210,475)))
    cons.extend(X('plains','southern_wilds','bottom',(640,110),(640,520)))
    cons.extend(X('plains','mountain_path','left',(1210,480),(65,480)))
    cons.extend(X('mountain_path','peak','top',(640,507),(640,108)))
    # Bring initial B1 free herb to a reliable known coordinate; maintain item IDs.
    for o in objects:
        if o['object_id']=='market_tomato':o['owner']='kart_lotta';o['respawn']=1
        if o['object_id']=='market_gold_pouch':o['value']=180;o['owner']='kart_lotta'
        if o['object_id']=='shop_bucket':o['stealable']=False
    world['npcs']=[
      {'npc_id':'naz','name':'Naz the Jerk','asset':'naz','area_id':'britrun_market','x':742,'y':447,'width':58,'height':82,
        'lines':['Have you been to the Gold District? I LIVE there.','Peasants like you do not belong in my neighborhood.',
                 'That vegetable stall smells positively common.']},
      {'npc_id':'inn_lout','name':'Boorish Inn Patron','asset':'lout','area_id':'inn_interior','x':850,'y':402,'width':64,'height':88},
      {'npc_id':'innkeeper','name':'The Innkeeper','asset':'vendor','area_id':'inn_interior','x':343,'y':257,'width':56,'height':77},
      {'npc_id':'fearmonger','name':'Fearmonger the Mage','asset':'mage','area_id':'mages_lab','x':642,'y':255,'width':65,'height':88},
      {'npc_id':'troll','name':'Frosty the Trollman','asset':'troll','area_id':'troll_cave','x':750,'y':303,'width':109,'height':144},
      {'npc_id':'giant','name':'Angry Giant','asset':'giant','area_id':'giant_camp','x':681,'y':301,'width':119,'height':193},
      {'npc_id':'mudcrab_a','name':'Territorial Mudcrab','asset':'mudcrab','area_id':'mudcrab_river','x':638,'y':395,'width':59,'height':43},
      {'npc_id':'mudcrab_b','name':'Very Angry Mudcrab','asset':'mudcrab','area_id':'mudcrab_river','x':789,'y':473,'width':59,'height':43}
    ]
    world['market_title']='The Spiffy Gift - A BritRun Adventure'
    return {'format':'luma-draw-engine','format_version':1,'engine':'SGG-C1-overlay','assets':assets,
            'world':world,'render_roles':{'female_vendor':'female_vendor'},'art_revision':'C1.0'}


def build_combined_assets(root=ROOT):
    root=Path(root)
    baseline=root/'luma_assets.json'
    output=root/'luma_assets_c1.json'
    if not baseline.is_file():
        raise FileNotFoundError(f'B1.0 original art is missing: {baseline}. Keep your original luma_assets.json alongside C1.0.')
    with baseline.open(encoding='utf-8') as f:base=json.load(f)
    if base.get('format')!='luma-draw-engine' or not base.get('world'):
        raise ValueError('Expected original B1.0 Luma Draw Engine assets')
    overlay=build_overlay(base)
    # The separate JSON is editable: artists can refine C1 recipes without touching Python.
    art_file=root/'c1_new_assets.json'
    if art_file.is_file():
        with art_file.open(encoding='utf-8') as f: art=json.load(f)
        if art.get('format')!='sgg-c1-art-overlay' or not isinstance(art.get('assets'),dict):
            raise ValueError('c1_new_assets.json has an invalid art-overlay format')
        overlay['assets']=art['assets']
    combined=dict(base)
    combined['assets']={**base['assets'],**overlay['assets']}
    combined['world']=overlay['world']
    combined['render_roles']={**base.get('render_roles',{}),**overlay['render_roles']}
    combined['art_revision']='C1.0 + preserved B1.0'
    # Always write from the original to ensure upgrades/restarts are reproducible.
    with output.open('w',encoding='utf-8') as f:json.dump(combined,f,separators=(',',':'),ensure_ascii=False)
    overlay_file=root/'c1_additions.json'
    with overlay_file.open('w',encoding='utf-8') as f:json.dump(overlay,f,indent=1,ensure_ascii=False)
    return output


if __name__=='__main__':
    print(build_combined_assets())
