from pathlib import Path
import json, math, random

HERE = Path(__file__).resolve().parent
JSON_PATH = HERE / 'luma_assets_e33.json'
BASE_PATH = HERE / 'F1.3_BASE_LUMA_ASSETS.json'
# Always start from the exact F1.3 baseline so this generator is idempotent.
doc = json.loads(BASE_PATH.read_text(encoding='utf-8'))

C = {
    'sky_top': (73,126,158), 'sky_mid': (112,151,165), 'sky_horizon': (183,190,172),
    'cloud': (225,229,213), 'hill_far': (91,123,124), 'hill_mid': (102,133,121),
    'grass': (91,119,79), 'grass_light': (111,139,88), 'grass_dark': (69,91,65),
    'shadow': (52,59,54), 'stone_shadow': (73,79,73), 'stone_side': (96,103,94),
    'stone': (129,134,122), 'stone_light': (155,158,140), 'stone_lit': (181,179,151),
    'mortar': (78,85,79), 'mortar_light': (193,187,158),
    'arch_outer': (73,79,73), 'arch_mid': (128,133,118), 'arch_light': (181,179,151),
    'arch_inner': (91,101,91), 'dark': (31,39,38), 'dark_mid': (47,56,52),
    'wood_dark': (64,40,30), 'wood': (104,61,37), 'wood_light': (137,83,48),
    'wood_glint': (163,106,63), 'iron': (55,61,57), 'gold': (204,171,111),
    'cobble_dark': (91,91,79), 'cobble': (151,145,123), 'cobble_light': (177,167,139),
}
cmd=[]
def rect(x,y,w,h,color,border=0,radius=0):
    d={'op':'rect','rect':[int(x),int(y),int(w),int(h)],'color':list(color)}
    if border: d['border']=int(border)
    if radius: d['radius']=int(radius)
    cmd.append(d)
def line(points,color,width=1):
    cmd.append({'op':'line','points':[[int(x),int(y)] for x,y in points],'color':list(color),'width':int(width)})
def poly(points,color,border=0):
    d={'op':'polygon','points':[[int(x),int(y)] for x,y in points],'color':list(color)}
    if border: d['border']=int(border)
    cmd.append(d)
def circle(x,y,r,color,border=0):
    d={'op':'circle','center':[int(x),int(y)],'radius':int(r),'color':list(color)}
    if border: d['border']=int(border)
    cmd.append(d)
def ellipse(x,y,w,h,color,border=0):
    d={'op':'ellipse','rect':[int(x),int(y),int(w),int(h)],'color':list(color)}
    if border: d['border']=int(border)
    cmd.append(d)

# -- Open sky, distant hills, and the green ground beneath the castle --
for y in range(0,361,8):
    t=min(1.0,y/361)
    col=tuple(round(C['sky_top'][i]*(1-t)+C['sky_horizon'][i]*t) for i in range(3))
    rect(0,y,1280,8,col)
# Clouds: soft clustered shapes, deliberately restrained.
for x,y,s in [(125,102,1.0),(940,90,.82),(1070,156,.55),(315,166,.48)]:
    ellipse(x,y,75*s,25*s,C['cloud']); ellipse(x+28*s,y-10*s,54*s,34*s,C['cloud']); ellipse(x+62*s,y+2*s,63*s,23*s,C['cloud'])
# The distant hills keep the same outdoors setting as the Castle Path.
poly([(0,345),(88,294),(164,326),(248,284),(342,333),(428,300),(520,346),(612,315),(700,343),(796,294),(895,329),(1006,287),(1112,328),(1196,292),(1280,330),(1280,470),(0,470)],C['hill_far'])
poly([(0,390),(112,344),(221,371),(333,334),(447,380),(561,348),(672,386),(788,340),(918,376),(1036,342),(1151,375),(1280,347),(1280,510),(0,510)],C['hill_mid'])
rect(0,410,1280,230,C['grass'])
poly([(0,422),(190,407),(370,427),(540,409),(700,430),(900,411),(1080,429),(1280,405),(1280,640),(0,640)],C['grass'])
# Gentle light/dark grass contours.
for pts in [ [(0,502),(240,480),(420,496),(610,470)], [(720,488),(930,467),(1120,489),(1280,472)],
             [(0,575),(220,553),(430,572)], [(890,565),(1100,548),(1280,561)] ]:
    line(pts,(111,137,88),2)
# Small distant shrubs and grass tufts.
for x,y in [(85,475),(168,542),(1080,475),(1170,530),(1030,590),(230,600),(1000,445)]:
    ellipse(x,y,32,12,(64,105,69)); ellipse(x+7,y-8,20,14,(81,126,77))
for x,y in [(63,560),(146,597),(1118,585),(1200,470),(300,470),(975,610),(1147,610)]:
    line([(x,y),(x-3,y-11)],(120,148,94),2); line([(x,y-6),(x+5,y-14)],(133,151,103),2)

# -- Foundation shadow and broad castle facade --
poly([(155,441),(205,382),(1070,382),(1125,443),(1087,501),(194,501)],C['stone_shadow'])
poly([(184,430),(220,385),(1060,385),(1096,430),(1068,478),(210,478)],(116,122,108))
# Wall wings; the open gate interrupts the center of this front wall.
rect(230,222,820,229,(125,131,120))
rect(230,222,820,18,(82,90,82))
# left and right towers: square, crenellated, no pointed roofs.
# Drop shadows first.
poly([(203,156),(420,156),(437,448),(220,448)],C['stone_shadow'])
poly([(860,156),(1077,156),(1060,448),(843,448)],C['stone_shadow'])
rect(213,154,205,288,(126,132,120))
rect(862,154,205,288,(126,132,120))
rect(213,154,205,12,(83,91,82))
rect(862,154,205,12,(83,91,82))
# Tower face highlights / edge faces.
rect(222,166,184,265,(151,154,137))
rect(871,166,184,265,(151,154,137))
rect(222,166,12,265,(106,114,104))
rect(1043,166,12,265,(104,111,101))
# Battlements along the top of each tower.
for x in [222,255,288,321,354,387]:
    rect(x,113,22,47,(94,102,94)); rect(x+3,116,16,40,(157,160,141))
    rect(x+5,119,11,4,(190,187,158))
for x in [871,904,937,970,1003,1036]:
    rect(x,113,22,47,(94,102,94)); rect(x+3,116,16,40,(157,160,141))
    rect(x+5,119,11,4,(190,187,158))
# Tower crowns and upper stone courses.
rect(213,151,205,10,(91,99,91)); rect(862,151,205,10,(91,99,91))
# Windows: narrow dark slits with stone lintels and interior crossbars.
for x in (305,951):
    rect(x-19,205,43,76,(73,80,75)); rect(x-13,211,31,64,(35,45,43))
    rect(x-9,214,3,58,(87,98,87)); rect(x+3,214,3,58,(87,98,87))
    rect(x-26,201,56,7,(181,179,151)); rect(x-24,282,52,5,(78,85,79))
    line([(x,212),(x,272)],(107,115,100),2)
# A few parapet openings on the outward tower faces.
for x in (245,275,1060,1030):
    rect(x,183,14,34,(74,82,76)); rect(x+3,187,8,25,(42,50,47))

# -- Stone blockwork on towers and the joining wall --
def masonry(x0,y0,x1,y1,row_h=23,seed=1,excluded=None):
    rnd=random.Random(seed)
    y=y0; row=0
    while y<y1:
        x=x0-(rnd.randint(0,28) if row%2 else 0)
        while x<x1:
            w=rnd.randint(24,53)
            xx=max(x0,x); ww=min(w,x1-xx)
            if ww>9:
                box=(xx,y,xx+ww,y+row_h-3)
                ok=True
                if excluded:
                    for ex in excluded:
                        if box[0]<ex[2] and box[2]>ex[0] and box[1]<ex[3] and box[3]>ex[1]: ok=False; break
                if ok:
                    fill=rnd.choice([(133,139,126),(143,146,131),(152,153,136),(123,132,120),(160,160,140)])
                    rect(xx,y,ww,row_h-3,fill)
                    line([(xx+2,y+2),(xx+ww-3,y+2)],(183,181,154),1)
                    line([(xx+3,y+row_h-4),(xx+ww-2,y+row_h-4)],(89,97,88),1)
            x += w+3
        y += row_h; row += 1
# Masonry pattern within tower surfaces.
masonry(237,170,409,432,21,seed=12,excluded=[(279,198,354,287)])
masonry(880,170,1052,432,21,seed=14,excluded=[(932,198,1007,287)])
# Joining wall bricks on both sides of arch.
masonry(420,235,500,439,20,seed=18)
masonry(780,235,862,439,20,seed=23)

# -- Central round-arched gatehouse. Layered rings are deliberately the same
# pale stone / deep charcoal palette as the Castle Path's distant arch.
def arch_points(cx,top,spring,base,rx,segments=16):
    pts=[(cx-rx,base),(cx-rx,spring)]
    for i in range(segments+1):
        theta=math.pi - math.pi*i/segments
        x=cx+math.cos(theta)*rx
        y=spring-(spring-top)*math.sin(theta)
        pts.append((round(x),round(y)))
    pts.extend([(cx+rx,base),(cx-rx,base)])
    return pts
# Deep offset silhouette and outer stone arch.
poly(arch_points(640,101,302,465,255),C['arch_outer'])
poly(arch_points(640,113,306,462,242),C['stone_shadow'])
poly(arch_points(640,127,311,458,228),C['arch_light'])
poly(arch_points(640,145,315,455,207),C['stone'])
poly(arch_points(640,161,321,453,187),C['dark'])
# Outer arch voussoirs: short radial joints and pale keystone blocks.
for i in range(15):
    theta=math.pi - math.pi*i/14
    xo=640+math.cos(theta)*228; yo=311-(311-127)*math.sin(theta)
    xi=640+math.cos(theta)*207; yi=315-(315-161)*math.sin(theta)
    line([(round(xo),round(yo)),(round(xi),round(yi))],(104,111,98),2)
# Keystone and ring highlights.
poly([(623,126),(640,116),(657,126),(654,151),(640,158),(626,151)],(192,188,160))
line([(640,117),(640,151)],(213,207,177),2)
# Inner tunnel ring and dark recess.
poly(arch_points(640,204,340,451,119),(57,67,61))
poly(arch_points(640,220,344,448,104),(31,39,38))
poly(arch_points(640,244,352,445,76),(46,56,51))
# Small distant inner stone doorway / lit wall beyond the open gate.
poly(arch_points(640,265,365,433,46),(111,124,99))
poly(arch_points(640,281,371,430,31),(146,155,119))
rect(620,371,40,58,(107,117,91))
# Raised portcullis / iron grille above the opening, as in the path view.
rect(536,176,208,13,(47,54,51)); rect(542,179,196,5,(115,116,99))
rect(541,186,198,5,(57,64,59))
for x in range(548,735,15):
    rect(x,187,4,44,(49,57,53)); poly([(x-2,228),(x+6,228),(x+2,235)],(49,57,53))
line([(536,232),(744,232)],(93,100,88),4)
# Open wooden gate leaves, angled back against the inner walls.
poly([(468,232),(509,218),(548,362),(519,407),(480,391),(459,300)],C['wood_dark'])
poly([(477,239),(509,229),(539,359),(516,392),(489,379),(471,302)],C['wood'])
poly([(487,246),(511,239),(530,356),(512,378),(497,369),(482,300)],C['wood_light'])
poly([(812,232),(771,218),(732,362),(761,407),(800,391),(821,300)],C['wood_dark'])
poly([(803,239),(771,229),(741,359),(764,392),(791,379),(809,302)],C['wood'])
poly([(793,246),(769,239),(750,356),(768,378),(783,369),(798,300)],C['wood_light'])
# Plank seams and iron straps on the doors.
for pts in [[(493,250),(505,369)],[(502,244),(515,375)],[(511,241),(524,362)],
            [(787,250),(775,369)],[(778,244),(765,375)],[(769,241),(756,362)]]:
    line(pts,C['wood_dark'],2)
line([(469,302),(537,322)],C['iron'],6); line([(743,322),(811,302)],C['iron'],6)
line([(480,369),(528,390)],C['iron'],5); line([(752,390),(800,369)],C['iron'],5)
for x,y in [(480,301),(520,314),(493,373),(523,386),(800,301),(760,314),(787,373),(757,386)]:
    circle(x,y,4,C['gold'])
# Heavy stone gate jambs and sloping buttresses.
poly([(423,342),(462,342),(482,454),(405,454)],(99,107,96))
poly([(432,350),(455,350),(468,445),(421,445)],(161,162,139))
poly([(857,342),(818,342),(798,454),(875,454)],(99,107,96))
poly([(848,350),(825,350),(812,445),(859,445)],(161,162,139))
line([(429,352),(452,352)],(202,197,166),3); line([(828,352),(851,352)],(202,197,166),3)

# -- Front approach: paving broadens toward the player, matching the Castle Path.
poly([(560,432),(720,432),(775,640),(505,640)],(70,76,66))
poly([(570,438),(710,438),(760,640),(520,640)],(132,127,108))
# Curved-looking paving rows with staggered individual stone faces.
rnd=random.Random(44)
for row,y in enumerate(range(446,638,18)):
    t=(y-446)/(638-446)
    half=70+58*t
    x0=640-half
    x=x0-(11 if row%2 else 0)
    while x<640+half:
        w=rnd.randint(15,31)
        if x+w>=x0 and x<=640+half:
            xx=max(int(x),int(x0)); ww=min(int(w),int(640+half-xx))
            if ww>7:
                h=rnd.randint(9,13)
                col=rnd.choice([(151,145,123),(166,158,132),(137,134,115),(177,167,139),(125,124,107)])
                poly([(xx+2,y),(xx+ww-2,y-1),(xx+ww,y+h-2),(xx+1,y+h)],col)
                line([(xx+3,y+1),(xx+ww-3,y)],(194,184,153),1)
        x += w+3
# Side lamp posts on the forecourt.
for x,y in [(344,419),(936,419)]:
    ellipse(x-10,y+34,20,7,(55,75,54))
    rect(x-3,y-8,6,40,(62,68,59)); rect(x-10,y-17,20,13,(78,75,61))
    rect(x-8,y-31,16,15,(177,151,87)); rect(x-6,y-29,12,11,(231,194,112))
    rect(x-11,y-33,22,4,(60,66,58)); rect(x-11,y-16,22,4,(60,66,58))
# Low stone bollards and grass tufts near the edges of the courtyard.
for x,y in [(168,453),(1110,453)]:
    ellipse(x-20,y+16,40,10,(61,81,58))
    poly([(x-14,y+10),(x-10,y-22),(x+10,y-22),(x+14,y+10)],(91,99,87))
    line([(x-9,y-17),(x+9,y-17)],(166,164,141),2)
# A few little conifers at far edges reinforce that this is the same outdoor approach.
for x,y,s in [(88,423,.75),(1195,423,.8),(116,535,.55),(1160,548,.62)]:
    rect(x-3,y,6,28,(74,75,54))
    for lev in range(4):
        yy=y-8-lev*15*s; ww=(29-lev*5)*s
        poly([(round(x-ww),round(yy+17*s)),(x,round(yy-7*s)),(round(x+ww),round(yy+17*s))],(35,91+lev*3,61))

# The architecture is intentionally built out of primitive Luma ops only.
new_asset = {'width':1280,'height':640,'commands':cmd}
doc['assets']['c1_bg_castle_exterior'] = new_asset
doc['version'] = 'SGGF1.4'
notes = doc.get('notes','').rstrip()
notes += ('\nSGGF1.4: rebuilt only the Castle Exterior background to match the F1.3 Castle Path castle: round pale-stone arch, deep vaulted opening, raised portcullis detail, open wooden gate leaves, square battlement towers, and a centered cobbled approach. Castle Path art, transitions, walkable corridor, entrance trigger, other scenes, gameplay, and save data are retained.')
doc['notes'] = notes
JSON_PATH.write_text(json.dumps(doc,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
print(f'Wrote {len(cmd)} Luma commands for castle exterior; total assets {len(doc["assets"])}')
