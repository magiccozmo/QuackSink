from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont
HERE=Path(__file__).resolve().parent
D=json.loads((HERE/'luma_assets_e33.json').read_text())
AS=D['assets']
def draw_asset(im,name,x,y,w=None,h=None):
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

im=Image.new('RGBA',(1280,640),(42,43,43,255))
draw_asset(im,'c1_bg_castle_exterior',0,0)
# Real interactable door object remains in the arch; it represents the inner hall door.
draw_asset(im,'door',589,325,97,115)
roles=D.get('render_roles',{})
# Player at the F1.3 return landing / courtyard approach.
draw_asset(im,roles.get('player','player'),620,469,40,58)
# Header overlay as the game UI does.
dr=ImageDraw.Draw(im); dr.rectangle((0,0,1280,44),fill=(22,18,31)); dr.line((0,43,1280,43),fill=(187,145,83),width=2)
try: font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16)
except: font=ImageFont.load_default()
dr.text((14,12),"SPIFFY'S GIFT  |  F1.4  |  BROWSER",font=font,fill=(239,225,195))
out=HERE/'F1.4_CASTLE_EXTERIOR_PREVIEW.png'
im.convert('RGB').save(out)
print(out)
