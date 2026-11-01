from pathlib import Path
import json, math
from PIL import Image, ImageDraw, ImageFont

HERE=Path(__file__).resolve().parent
DATA=HERE/'luma_assets_e33.json'
doc=json.loads(DATA.read_text(encoding='utf-8'))
cmd=[]

# Exterior-matched castle palette: grey-green limestone, pale cut-stone trim,
# deep shadowed openings, dark timber, iron and warm gold.
C={
 'void':(35,40,39),'ceiling':(53,57,53),'ceiling_hi':(84,87,76),
 'wall_shadow':(73,79,73),'wall':(116,123,111),'wall_mid':(132,137,122),
 'stone':(145,149,132),'stone_hi':(177,177,151),'stone_lit':(195,190,160),
 'stone_dark':(91,99,89),'mortar':(76,83,77),'mortar_hi':(177,172,147),
 'arch_outer':(73,80,73),'arch_mid':(128,135,119),'arch_hi':(180,179,151),
 'dark':(27,35,34),'dark_mid':(43,52,49),'glass':(40,75,97),'glass_hi':(56,101,124),
 'iron':(45,54,53),'iron_hi':(102,109,97),'wood':(94,54,34),'wood_hi':(137,82,47),
 'gold':(204,171,111),'gold_hi':(244,211,142),'banner':(66,43,91),'banner_hi':(113,75,145),
 'floor':(100,94,82),'floor_hi':(132,124,104),'floor_shadow':(60,59,53),
 'carpet':(91,37,56),'carpet_hi':(128,53,73),
 'flame':(255,193,91),'armor':(135,143,134),'armor_hi':(190,190,166),
}

def rect(x,y,w,h,col,border=0,radius=0):
    d={'op':'rect','rect':[int(x),int(y),int(w),int(h)],'color':list(col)}
    if border:d['border']=int(border)
    if radius:d['radius']=int(radius)
    cmd.append(d)
def line(points,col,width=1):
    cmd.append({'op':'line','points':[[int(x),int(y)] for x,y in points],'color':list(col),'width':int(width)})
def poly(points,col,border=0):
    d={'op':'polygon','points':[[int(x),int(y)] for x,y in points],'color':list(col)}
    if border:d['border']=int(border)
    cmd.append(d)
def ellipse(x,y,w,h,col,border=0):
    d={'op':'ellipse','rect':[int(x),int(y),int(w),int(h)],'color':list(col)}
    if border:d['border']=int(border)
    cmd.append(d)
def circle(x,y,r,col,border=0):
    d={'op':'circle','center':[int(x),int(y)],'radius':int(r),'color':list(col)}
    if border:d['border']=int(border)
    cmd.append(d)

def arch_points(cx,top,r,steps=32):
    cy=top+r
    return [(cx+r*math.cos(math.radians(a)),cy+r*math.sin(math.radians(a))) for a in range(180,361, max(1,180//steps))]

def draw_arch(cx,top,r,bottom,thick,accent=True):
    """A deep, rounded stone portal with individually cut voussoir blocks."""
    cy=top+r
    outer=arch_points(cx,top,r,36)
    # Full exterior shadow and inset opening.
    poly([(cx-r,bottom)]+outer+[(cx+r,bottom)],C['arch_outer'])
    ri=r-thick
    inner=arch_points(cx,top+thick,ri,36)
    poly([(cx-ri,bottom)]+inner+[(cx+ri,bottom)],C['dark'])
    # Pale cut-stone ring, divided into wedge-shaped blocks.
    angles=list(range(180,0,-15))
    for a1,a2 in zip(angles[:-1],angles[1:]):
        pts=[]
        for a in (a1,a1+(a2-a1)/3,a2):
            pts.append((cx+r*math.cos(math.radians(a)),cy+r*math.sin(math.radians(a))))
        for a in (a2,a2-(a2-a1)/3,a1):
            pts.append((cx+ri*math.cos(math.radians(a)),cy+ri*math.sin(math.radians(a))))
        idx=(a1//15)%4
        fill=[C['arch_mid'],C['stone'],C['arch_hi'],C['stone_hi']][idx]
        poly(pts,fill)
        line([pts[0],pts[1]],C['mortar'],2)
    # Side jambs and their bevels.
    rect(cx-r,bottom-r if False else cy,thick,bottom-cy,C['arch_mid'])
    rect(cx+ri,cy,thick,bottom-cy,C['arch_mid'])
    rect(cx-r,cy,7,bottom-cy,C['arch_outer'])
    rect(cx+r-7,cy,7,bottom-cy,C['arch_outer'])
    line([(cx-r+8,cy+4),(cx-r+8,bottom-6)],C['stone_hi'],2)
    line([(cx+r-8,cy+4),(cx+r-8,bottom-6)],C['stone_hi'],2)
    # Key stone centered at the crown.
    poly([(cx-13,top+7),(cx,top-2),(cx+13,top+7),(cx+10,top+26),(cx,top+32),(cx-10,top+26)],C['stone_lit'])
    line([(cx,top+8),(cx,top+27)],C['mortar'],2)
    # Threshold.
    rect(cx-r-5,bottom-8,2*r+10,12,C['stone_dark'])
    rect(cx-r+3,bottom-8,2*r-6,5,C['stone_hi'])

# -- Shadowed upper vault and continuous limestone rear wall --
rect(0,0,1280,640,C['void'])
rect(0,42,1280,381,C['wall_shadow'])
rect(0,62,1280,343,C['wall'])
# Upper vault: deep ceiling field with broad stone ribs.
poly([(0,0),(1280,0),(1280,92),(1110,60),(950,44),(800,33),(640,27),(480,33),(320,44),(170,60),(0,92)],C['ceiling'])
line([(0,90),(170,60),(320,44),(480,33),(640,27),(800,33),(950,44),(1110,60),(1280,90)],C['ceiling_hi'],7)
for x in (0,320,640,960,1280):
    line([(x,0),(x,43 if x in (320,960) else 59)],C['wall_shadow'],9)
    line([(x-7,0),(x-7,43 if x in (320,960) else 59)],C['arch_hi'],2)
# Horizontal stone courses with alternating vertical joints.
for y in range(82,414,48):
    line([(0,y),(1280,y)],C['mortar'],3)
    offset=0 if ((y//48)%2==0) else 62
    for x in range(offset-100,1380,124):
        line([(x,y),(x,y+48)],C['mortar'],3)
        line([(x+3,y+3),(x+3,y+44)],C['stone_dark'],1)
    line([(0,y+3),(1280,y+3)],(148,150,133),1)
# Decorative cornice along the wall/ceiling junction.
rect(0,61,1280,17,C['stone_dark'])
rect(0,61,1280,5,C['stone_lit'])
rect(0,77,1280,4,C['mortar'])

# -- Great hall pilasters: heavy masonry piers with stepped capitals/bases --
def pier(x,w=54):
    rect(x-8,69,w+16,20,C['arch_outer'])
    rect(x-3,72,w+6,10,C['stone_lit'])
    rect(x,82,w,319,C['stone_dark'])
    rect(x+6,86,w-12,310,C['stone'])
    rect(x+11,91,5,300,C['stone_hi'])
    rect(x+w-16,87,5,307,C['stone_dark'])
    rect(x-12,391,w+24,25,C['arch_outer'])
    rect(x-6,393,w+12,14,C['stone_hi'])
    rect(x-13,408,w+26,12,C['stone_dark'])
for x in (74,452,828,1186): pier(x,50)
# Small carved panels on the pier faces.
for x in (92,470,846,1204):
    rect(x,113,14,188,C['stone_dark'])
    rect(x+3,117,8,180,C['stone_mid'] if 'stone_mid' in C else C['wall_mid'])
    line([(x+4,127),(x+4,285)],C['stone_lit'],2)
    rect(x-1,145,16,5,C['mortar_hi'])
    rect(x-1,270,16,5,C['mortar_hi'])

# -- Two high arched blue-glass windows, seated into the masonry --
def window(cx,top,r,bottom):
    draw_arch(cx,top,r,bottom,13)
    # Deep blue glass in the portal, with cool reflection panes.
    poly([(cx-r+17,bottom-14)]+arch_points(cx,top+18,r-18,32)+[(cx+r-17,bottom-14)],C['glass'])
    poly([(cx-r+25,bottom-18)]+arch_points(cx,top+24,r-26,32)+[(cx-5,bottom-18)],C['glass_hi'])
    rect(cx-3,top+31,6,bottom-top-42,C['stone_lit'])
    line([(cx-r+18,(top+bottom)//2),(cx+r-18,(top+bottom)//2)],C['stone_hi'],6)
    line([(cx-r+20,top+58),(cx+r-20,top+58)],(94,125,139),2)
    # Lower sill and carved supports.
    rect(cx-r-12,bottom-8,2*r+24,16,C['stone_lit'])
    rect(cx-r-8,bottom+8,2*r+16,8,C['arch_outer'])
window(190,119,57,316)
window(797,119,57,316)

# -- Royal standard: purple and gold crest, kept in its established position --
rect(249,101,103,76,C['arch_outer'])
rect(256,107,89,65,C['banner'])
poly([(256,107),(345,107),(345,169),(300,154),(256,169)],C['banner_hi'])
line([(300,108),(300,152)],(77,55,103),2)
circle(300,132,18,C['gold'])
circle(300,132,8,C['banner'])
rect(295,177,10,13,C['gold'])

# -- Three matching portals: same pale limestone arches and deep recesses as the exterior --
# The central portal is grander; the side portals preserve current door object positions.
draw_arch(297,190,77,411,17)
draw_arch(640,160,96,418,22)
draw_arch(984,194,76,410,17)
# Dark arch recesses are intentionally deep above each interactable door.
# Recess panel stone ribs / engraved vertical lines give the interior depth.
for cx,top,r,bottom in ((297,190,77,411),(640,160,96,418),(984,194,76,410)):
    for side in (-1,1):
        x=int(cx+side*(r-25))
        line([(x,top+r+4),(x,bottom-18)],C['arch_outer'],3)
        line([(x+side*5,top+r+6),(x+side*5,bottom-18)],C['stone_dark'],2)
# Additional voussoir highlights echo the exterior's carved gate arch.
for cx,top,r in ((297,190,77),(640,160,96),(984,194,76)):
    cy=top+r
    for a in range(198,343,24):
        x=cx+r*math.cos(math.radians(a)); y=cy+r*math.sin(math.radians(a))
        x2=cx+(r-12)*math.cos(math.radians(a)); y2=cy+(r-12)*math.sin(math.radians(a))
        line([(x,y),(x2,y2)],C['mortar_hi'],2)

# -- Carved wall panels and a subtle secret seam beside the vault gate --
# This panel is deliberately understated so the existing platter puzzle remains discoverable.
rect(1029,208,7,190,C['stone_dark'])
line([(1032,214),(1032,391)],C['mortar'],2)
line([(1037,218),(1037,386)],C['stone_hi'],1)
rect(1081,220,42,164,C['wall_mid'])
rect(1085,225,34,154,C['wall'])
line([(1088,230),(1116,230)],C['stone_lit'],2)
line([(1088,373),(1116,373)],C['stone_dark'],2)

# -- Wall sconces: iron brackets and warm golden firelight --
def sconce(x,y):
    rect(x-6,y+23,12,89,C['iron'])
    rect(x-14,y+31,28,8,C['iron_hi'])
    line([(x,y+27),(x,y+8)],C['iron'],5)
    line([(x-1,y+13),(x-16,y+2)],C['iron'],4)
    poly([(x-13,y+8),(x-10,y-5),(x,y-13),(x+10,y-5),(x+13,y+8),(x+5,y+15),(x-6,y+15)],C['gold'])
    ellipse(x-11,y-22,22,26,C['flame'])
    ellipse(x-6,y-22,12,15,C['gold_hi'])
    ellipse(x-2,y-25,5,9,(255,237,183))
    line([(x-19,y+8),(x-26,y+17)],C['iron_hi'],3)
    line([(x+19,y+8),(x+26,y+17)],C['iron_hi'],3)
sconce(555,202); sconce(1115,202)

# -- Stone sentinels on low plinths, as guardian statues rather than blank mannequins --
def sentinel(cx,base):
    rect(cx-27,base-10,54,11,C['arch_outer'])
    rect(cx-22,base-21,44,12,C['stone_dark'])
    rect(cx-18,base-26,36,7,C['stone_hi'])
    # greaves and boots
    poly([(cx-16,base-88),(cx-3,base-86),(cx-5,base-29),(cx-19,base-29)],C['armor'])
    poly([(cx+3,base-86),(cx+16,base-88),(cx+19,base-29),(cx+5,base-29)],C['armor'])
    rect(cx-19,base-34,17,7,C['stone_dark']); rect(cx+3,base-34,17,7,C['stone_dark'])
    # body / breastplate / shoulders
    poly([(cx-19,base-92),(cx-30,base-105),(cx-22,base-119),(cx-9,base-124),(cx+9,base-124),(cx+22,base-119),(cx+30,base-105),(cx+19,base-92),(cx+14,base-60),(cx-14,base-60)],C['armor'])
    poly([(cx-13,base-112),(cx,base-119),(cx+13,base-112),(cx+10,base-76),(cx,base-66),(cx-10,base-76)],C['stone_hi'])
    line([(cx,base-116),(cx,base-73)],C['stone_dark'],2)
    line([(cx-9,base-93),(cx+9,base-93)],C['arch_outer'],2)
    # arms and gauntlets
    poly([(cx-23,base-111),(cx-34,base-98),(cx-29,base-69),(cx-19,base-67),(cx-14,base-89)],C['armor'])
    poly([(cx+23,base-111),(cx+34,base-98),(cx+29,base-69),(cx+19,base-67),(cx+14,base-89)],C['armor'])
    line([(cx-28,base-99),(cx-21,base-91)],C['stone_hi'],2)
    line([(cx+28,base-99),(cx+21,base-91)],C['stone_hi'],2)
    # crowned helmet with visor slit
    poly([(cx-18,base-124),(cx-16,base-145),(cx-7,base-155),(cx+7,base-155),(cx+16,base-145),(cx+18,base-124),(cx+11,base-116),(cx-11,base-116)],C['armor'])
    poly([(cx-12,base-143),(cx,base-151),(cx+12,base-143),(cx+10,base-134),(cx-10,base-134)],C['stone_hi'])
    line([(cx-10,base-130),(cx+10,base-130)],C['iron'],3)
    poly([(cx-4,base-155),(cx,base-170),(cx+4,base-155)],C['gold'])
    line([(cx-24,base-109),(cx+24,base-109)],C['stone_lit'],2)
# Sentinel bases and silhouettes positioned to preserve their existing spaces.
sentinel(435,416); sentinel(1149,416)

# -- Stone floor, flagstone perspective and crimson/gold processional runner --
rect(0,418,1280,222,C['floor'])
rect(0,418,1280,10,C['floor_shadow'])
line([(0,432),(1280,432)],C['floor_hi'],3)
# Perspective seams converge on the central hall vanishing point.
for x in (-180,-30,120,270,420,540,640,740,860,1010,1160,1310,1460):
    line([(640,420),(x,640)],C['floor_shadow'],3)
# Horizontal flagstone courses with progressively wider spacing.
for y in (447,476,511,552,598):
    line([(0,y),(1280,y)],C['floor_shadow'],3)
    line([(0,y+3),(1280,y+3)],(132,124,106),1)
# A few offset slab highlights, restrained to avoid visual noise.
for y,xs in ((454,(75,330,900,1145)),(489,(190,520,760,1060)),(526,(80,410,830,1195)),(570,(260,610,970))):
    for x in xs:
        line([(x,y),(x+48,y)],C['floor_hi'],2)
        line([(x+4,y+4),(x+44,y+4)],C['floor_shadow'],1)
# Carpet and gold edging.
poly([(613,418),(667,418),(796,640),(484,640)],C['carpet'])
poly([(619,420),(661,420),(780,640),(500,640)],C['carpet_hi'])
line([(610,418),(480,640)],C['gold'],5)
line([(670,418),(800,640)],C['gold'],5)
line([(614,423),(486,640)],C['gold_hi'],1)
line([(666,423),(794,640)],C['gold_hi'],1)
for y,x1,x2 in ((455,607,673),(492,584,696),(540,555,725),(596,526,754)):
    line([(x1,y),(x2,y)],C['gold'],4)
    line([(x1+8,y+4),(x2-8,y+4)],C['carpet'],1)
# Floor/wall threshold blocks along the sides of the carpet.
for x in (8,130,252,374,906,1028,1150):
    rect(x,420,68,8,C['stone_dark'])
    line([(x+4,421),(x+62,421)],C['stone_hi'],1)

# Narrow stone balustrade/baseboard ties wall into floor.
rect(0,404,1280,15,C['arch_outer'])
rect(0,404,1280,5,C['stone_hi'])
rect(0,415,1280,4,C['mortar'])

# Install only the castle hall background recipe. World and object definitions untouched.
doc['assets']['c1_bg_castle_hall']={'width':1280,'height':640,'commands':cmd}
doc['version']='SGGF1.5-PREVIEW'
doc['notes']=(doc.get('notes','').rstrip()+"\nF1.5 design preview: castle hall art direction aligned to F1.4 exterior fortress stone, pale cut-stone arch rings, deep vaulted portals, warm gold/iron fixtures, stone flagstone floor and burgundy runner. This preview changes only the castle hall background recipe.")

# Save preview recipe separately; do not replace F1.4 release source.
preview_json=HERE/'luma_assets_f15_preview.json'
preview_json.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# Pillow renderer for preview: background + original live door/secret-seam/player assets.
W,H=1280,640
im=Image.new('RGBA',(W,H),(0,0,0,255))
draw=ImageDraw.Draw(im)
AS=doc['assets']
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
# Exact existing scene objects; their locations and dimensions are not changed.
for oid in ('lab_door','castle_exit','vault_locked_door','vault_wall_seam'):
    obj=next(o for o in doc['world']['objects'] if o['object_id']==oid)
    render_asset(obj['kind'],obj['x'],obj['y'],obj['width'],obj['height'])
# Existing player placed on the current arrival/runway position.
render_asset('player',620,469,40,58)
# Game header and status strip for an apples-to-apples scene preview.
dr=ImageDraw.Draw(im)
dr.rectangle((0,0,1280,44),fill=(22,18,31)); dr.line((0,43,1280,43),fill=(187,145,83),width=2)
dr.rectangle((0,44,1280,46),fill=(40,29,35))
try: font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16); small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',13)
except: font=ImageFont.load_default(); small=font
dr.text((15,12),"SPIFFY'S GIFT  |  F1.5 DESIGN PREVIEW  |  BROWSER",font=font,fill=(239,225,195))
dr.rectangle((0,614,1280,640),fill=(35,28,31)); dr.line((0,614,1280,614),fill=(166,133,91),width=2)
dr.text((14,620),'CASTLE: point + E to interact; walk through doors; platter + wall seam for vault.',font=small,fill=(245,236,214))
preview=HERE/'F1.5_CASTLE_HALL_PREVIEW.png'
im.convert('RGB').save(preview,quality=95)
print('commands',len(cmd))
print('preview',preview)
print('recipe',preview_json)
