"""Render the F1.3 Castle Path scene preview from the real Luma recipes."""
from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
DOC = json.loads((HERE/'luma_assets_e33.json').read_text(encoding='utf-8'))
ASSETS = DOC['assets']
SCALE = 3


def draw_recipe(im, name, x, y, w=None, h=None):
    asset = ASSETS[name]
    w = w if w is not None else asset['width']
    h = h if h is not None else asset['height']
    sx, sy = w/asset['width'], h/asset['height']
    dr = ImageDraw.Draw(im)
    for c in asset['commands']:
        color = tuple(c.get('color',(255,255,255)))
        op = c['op']
        width = max(1, round(c.get('width',1)*SCALE*(sx+sy)/2))
        border = max(0, round(float(c.get('border',0))*SCALE*(sx+sy)/2))
        if op in ('rect','ellipse'):
            rx,ry,rw,rh = c['rect']
            box=((x+rx*sx)*SCALE,(y+ry*sy)*SCALE,
                 (x+(rx+rw)*sx)*SCALE,(y+(ry+rh)*sy)*SCALE)
            if op=='rect':
                if border: dr.rectangle(box,outline=color,width=border)
                else: dr.rectangle(box,fill=color)
            else:
                if border: dr.ellipse(box,outline=color,width=border)
                else: dr.ellipse(box,fill=color)
        elif op=='polygon':
            points=[((x+px*sx)*SCALE,(y+py*sy)*SCALE) for px,py in c['points']]
            if border: dr.line(points+[points[0]],fill=color,width=border,joint='curve')
            else: dr.polygon(points,fill=color)
        elif op=='line':
            points=[((x+px*sx)*SCALE,(y+py*sy)*SCALE) for px,py in c['points']]
            dr.line(points,fill=color,width=width,joint='curve')
        elif op=='circle':
            cx,cy=c['center']; r=c['radius']*SCALE*(sx+sy)/2
            box=((x+cx*sx)*SCALE-r,(y+cy*sy)*SCALE-r,
                 (x+cx*sx)*SCALE+r,(y+cy*sy)*SCALE+r)
            if border: dr.ellipse(box,outline=color,width=border)
            else: dr.ellipse(box,fill=color)

scene=Image.new('RGBA',(1280*SCALE,640*SCALE),(42,43,43,255))
draw_recipe(scene,'c1_bg_castle_path',0,0,1280,640)

# Place Spiffy at the F1.2 threshold location, using the same authored sprite
# dimensions and baseline render anchor as LumaInterface._draw_game_scene.
player = DOC['world'].get('player',{})
roles = DOC.get('render_roles',{})
pw,ph=int(player.get('draw_width',40)),int(player.get('draw_height',58))
px,py=791.2,371.2
player_x, player_y = round(px-pw/2), round(py-ph*.7)
draw_recipe(scene,roles.get('player','player'),player_x,player_y,pw,ph)

# Reproduce the F1.3 Castle Exterior marker and its matching transition label.
fx,fy=-0.8303,-0.5573
lx,ly=0.5573,-0.8303
ax,ay=791.2,371.2
mx,my=round(ax+fx*40),round(ay+fy*40)
local=[(14,0),(-4,-13),(-4,-5),(-12,-5),(-12,5),(-4,5),(-4,13)]
points=[(round(mx+fx*a+lx*b)*SCALE,round(my+fy*a+ly*b)*SCALE) for a,b in local]
draw=ImageDraw.Draw(scene)
draw.polygon(points,fill=(30,28,37,255))
draw.line(points+[points[0]],fill=(250,209,104,255),width=3*SCALE,joint='curve')
label_x=round(mx+lx*56+fx*4)
label_y=round(my+ly*56+fy*4)
try:
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',15*SCALE)
except OSError:
    font=ImageFont.load_default()
caption='Castle Exterior'
bbox=draw.textbbox((0,0),caption,font=font)
tw,th=bbox[2]-bbox[0],bbox[3]-bbox[1]
panel=(label_x*SCALE-tw//2-5*SCALE,label_y*SCALE-th//2-2*SCALE,
       label_x*SCALE+tw//2+5*SCALE,label_y*SCALE+th//2+2*SCALE)
draw.rounded_rectangle(panel,radius=3*SCALE,fill=(28,27,32,255))
draw.text((label_x*SCALE-tw//2,label_y*SCALE-th//2-bbox[1]),caption,
          font=font,fill=(251,232,172,255))

# Add the standard in-game header bar to show the actual release label.
draw.rectangle((0,0,1280*SCALE,44*SCALE),fill=(22,18,31,255))
draw.line((0,43*SCALE,1280*SCALE,43*SCALE),fill=(187,145,83,255),width=2*SCALE)
header='SPIFFY\'S GIFT  |  F1.3  |  BROWSER'
draw.text((14*SCALE,12*SCALE),header,font=font,fill=(239,225,195,255))

out=HERE/'F1.3_CASTLE_PATH_PREVIEW.png'
scene.convert('RGB').resize((1280,640),Image.Resampling.LANCZOS).save(out)
print(out)
