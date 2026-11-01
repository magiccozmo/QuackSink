import json
from pathlib import Path
from PIL import Image, ImageDraw
p=Path(__file__).with_name('luma_assets_e33.json')
d=json.loads(p.read_text())
asset=d['assets']['c1_bg_castle_exterior']
S=3
im=Image.new('RGB',(1280*S,640*S),(0,0,0)); dr=ImageDraw.Draw(im)
for c in asset['commands']:
 op=c['op']; col=tuple(c.get('color',(255,255,255))); w=max(1,round(c.get('width',1)*S)); b=max(0,round(c.get('border',0)*S))
 if op in ('rect','ellipse'):
  x,y,ww,hh=c['rect']; box=(x*S,y*S,(x+ww)*S,(y+hh)*S)
  if op=='rect': dr.rectangle(box,fill=col if b==0 else None,outline=col if b else None,width=b or 1)
  else: dr.ellipse(box,fill=col if b==0 else None,outline=col if b else None,width=b or 1)
 elif op=='polygon':
  pts=[(x*S,y*S) for x,y in c['points']]
  if b: dr.line(pts+[pts[0]],fill=col,width=b,joint='curve')
  else: dr.polygon(pts,fill=col)
 elif op=='line': dr.line([(x*S,y*S) for x,y in c['points']],fill=col,width=w,joint='curve')
 elif op=='circle':
  x,y=c['center']; r=c['radius']*S; box=((x*S-r),(y*S-r),(x*S+r),(y*S+r))
  if b: dr.ellipse(box,outline=col,width=b)
  else: dr.ellipse(box,fill=col)
 else: raise ValueError(op)
im.resize((1280,640),Image.Resampling.LANCZOS).save('/mnt/data/sgg_f14_work/base/F1.3_EXISTING_CASTLE_EXTERIOR.png')
