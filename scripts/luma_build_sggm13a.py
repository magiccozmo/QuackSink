import os, json, shutil, zipfile, tarfile, hashlib, math, pathlib, subprocess, sys, copy, ast

REPO=pathlib.Path(os.environ["GITHUB_WORKSPACE"])
TMP=pathlib.Path(os.environ["RUNNER_TEMP"])
WORK=TMP/"sggm13_work"
SRC=WORK/"source"; DEP=WORK/"deploy"
OUT=TMP/"delivery"
SRC.mkdir(parents=True); DEP.mkdir(parents=True); OUT.mkdir(parents=True)
base=REPO/"ARCHIVES 8-30-2026/SGG/sggweb"
srczip=base/"SGGM1.1_SOURCE.zip"; depzip=base/"SGGM1.1_COMPLETE_CLOUDFLARE_SITE.zip"
subprocess.run(["unzip","-q",str(srczip),"-d",str(SRC)],check=True)
subprocess.run(["unzip","-q",str(depzip),"-d",str(DEP)],check=True)
SRC_DEP=SRC/"deploy"; REL=DEP/"SGGM1.3a"; SRC_REL=SRC_DEP/"SGGM1.3a"
def writej(p,o): p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def sha(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
 return h.hexdigest()
def inside(x,y,r):
 a,b,w,h=r; return a<=x<=a+w and b<=y<=b+h
def safe(l,x,y):
 samples=((x,y),(x-10,y-13),(x+10,y-13),(x-10,y+13),(x+10,y+13))
 if not all(any(inside(sx,sy,r) for r in l.get("walkmesh",[])) for sx,sy in samples): return False
 for a,b,w,h in l.get("blocked",[]):
  if x-10<a+w and x+10>a and y-13<b+h and y+13>b: return False
 return 0<=x<=l["width"] and 0<=y<=l["height"]
def segments(ps):
 out=[]
 for a,b in zip(ps,ps[1:]):
  dx=b[0]-a[0]; dy=b[1]-a[1]; n=max(1,math.ceil(math.hypot(dx,dy)/15))
  out.extend([(a[0]+dx*i/n,a[1]+dy*i/n) for i in range(n)])
 out.append(tuple(ps[-1])); return out
def landing(l,x,y):
 if safe(l,x,y): return True
 for r in (20,36,52,72,96,124,156,190,230,275,320):
  for i in range(24):
   a=math.tau*i/24
   if safe(l,x+math.cos(a)*r,y+math.sin(a)*r): return True
 return False

mp=SRC/"assets/m1_world_layers.json"
original=json.loads(mp.read_text(encoding="utf-8")); data=copy.deepcopy(original)
data["version"]="SGGM1.3a"; data["start"]={"layer":"city_exterior","x":3400,"y":1490}; layers={x["id"]:x for x in data["layers"]}; c=layers["city_exterior"]
c["walkmesh"]=[
 [1810,760,1160,620],[2050,620,650,220],[2820,880,550,420],
 [3060,1110,600,610],[1360,1090,510,270],[1320,450,340,800],
 [1100,170,720,510],[1320,1210,360,400],[1320,1370,1250,330],
 [2070,1430,1590,260],[2760,1260,480,430]]
c["paths"]=[
 {"points":[[3400,1600],[3400,1320],[3260,1250],[3090,1150],[2890,1130],[2700,1150]],"width":145,"style":"road"},
 {"points":[[1810,1220],[1640,1220],[1450,1220]],"width":125,"style":"road"},
 {"points":[[1450,1220],[1450,1010],[1450,790],[1450,570],[1450,500]],"width":125,"style":"road"},
 {"points":[[1450,1220],[1450,1370],[1640,1490],[1900,1535]],"width":125,"style":"road"},
 {"points":[[1900,1535],[2320,1535],[2740,1550],[3090,1600],[3400,1610]],"width":125,"style":"road"},
 {"points":[[2350,840],[2350,720]],"width":72,"style":"road"},
 {"points":[[2930,1090],[3010,1060]],"width":76,"style":"road"},
 {"points":[[2950,1530],[2950,1460]],"width":64,"style":"road"}]
c["landmarks"]=[
 {"id":"market","name":"Market Square — Kart-lotta's Stand","kind":"market","x":2350,"y":1000,"w":200,"h":145},
 {"id":"alchemy_exterior","name":"Alchemy Shop","kind":"building","x":3160,"y":940,"w":260,"h":220},
 {"id":"inn_exterior","name":"Tipsy Turnip Inn","kind":"building","x":2350,"y":555,"w":420,"h":250},
 {"id":"gold_district","name":"Gold District","kind":"district","x":1900,"y":1510,"w":420,"h":230},
 {"id":"castle_path","name":"Castle Path","kind":"landmark","x":1450,"y":760,"w":220,"h":180},
 {"id":"castle_exterior","name":"Castle Exterior","kind":"castle","x":1450,"y":315,"w":420,"h":270},
 {"id":"little_lantern","name":"The Little Lantern","kind":"building","x":2950,"y":1365,"w":180,"h":140},
 {"id":"front_gate","name":"City Gate","kind":"gate","x":3400,"y":1635,"w":260,"h":220}]
c["npcs"]=[
 {"id":"kart_lotta","name":"Kart-lotta","x":2350,"y":1135,"role":"merchant"},
 {"id":"naz","name":"Naz","x":2040,"y":1125,"role":"merchant"},
 {"id":"britrun_guard","name":"BritRun Guard","x":3370,"y":1460,"role":"guard"},
 {"id":"cozmo_city","name":"Cozmo","x":2690,"y":1125,"role":"magician"}]
c["portals"]=[
 {"id":"city_to_inn","name":"Tipsy Turnip Door","x":2350,"y":720,"radius":54,"target_layer":"inn_interior","target_x":1420,"target_y":420,"style":"door"},
 {"id":"city_to_alchemy","name":"Alchemy Shop Door","x":3010,"y":1060,"radius":52,"target_layer":"alchemy_shop","target_x":1420,"target_y":420,"style":"door"},
 {"id":"city_to_castle_hall","name":"Castle Gate","x":1450,"y":500,"radius":62,"target_layer":"castle_hall","target_x":1430,"target_y":690,"style":"gate"},
 {"id":"city_to_little_lantern","name":"Little Lantern Door","x":2950,"y":1460,"radius":48,"target_layer":"little_lantern","target_x":1420,"target_y":420,"style":"door"},
 {"id":"city_gate_to_countryside","name":"City Gate — Countryside","x":3400,"y":1610,"radius":76,"target_layer":"countryside","target_x":390,"target_y":1010,"style":"gate"}]
c["blocked"]=[
 [2140,430,420,250],[3030,825,260,210],[1290,180,420,270],
 [2860,1295,180,135],[2255,930,190,120]]
arrivals={"countryside":("countryside_to_city",3400,1490),
 "inn_interior":("inn_to_city",2350,835),
 "alchemy_shop":("alchemy_to_city",2945,1130),
 "castle_hall":("hall_to_city",1450,610),
 "little_lantern":("lantern_to_city",2950,1530)}
for lid,(pid,x,y) in arrivals.items():
 ps=[p for p in layers[lid]["portals"] if p["id"]==pid and p["target_layer"]=="city_exterior"]
 assert len(ps)==1; ps[0]["target_x"]=x; ps[0]["target_y"]=y
assert len(data["layers"])==11 and sum(len(x.get("portals",[])) for x in data["layers"])==19
assert len(c["landmarks"])==8 and len(c["npcs"])==4 and len(c["portals"])==5
for l in data["layers"]:
 for p in l.get("portals",[]): assert safe(layers[p["target_layer"]],p["target_x"],p["target_y"]), (l["id"],p["id"],"arrival")
for p in c["portals"]: assert safe(c,p["x"],p["y"]),("city portal",p["id"])
for n in c["npcs"]: assert safe(c,n["x"],n["y"]),("npc",n["id"])
for lm in c["landmarks"]: assert landing(c,lm["x"],lm["y"]),("landmark",lm["id"])
for pi,p in enumerate(c["paths"]):
 for x,y in segments(p["points"]): assert safe(c,x,y),("path",pi,x,y)
for l in original["layers"]:
 if l["id"]=="city_exterior": continue
 nl=layers[l["id"]]
 if l["id"] not in arrivals: assert l==nl,l["id"]
 else:
  ol={x["id"]:x for x in l.get("portals",[])}; nn={x["id"]:x for x in nl.get("portals",[])}
  for pid,old in ol.items():
   new=nn[pid]
   if pid==arrivals[l["id"]][0]:
    ex=arrivals[l["id"]]
    for k,v in old.items():
     want=ex[1] if k=="target_x" else ex[2] if k=="target_y" else v
     assert new.get(k)==want,(l["id"],pid,k)
   else: assert old==new,(l["id"],pid)
maptext=json.dumps(data,ensure_ascii=False,indent=2)+"\n"
for p in [SRC/"assets/m1_world_layers.json",SRC/"m1_world_layers.json",DEP/"m1_world_layers.json"]: p.write_text(maptext,encoding="utf-8")

# Real engine startup validation: execute the unchanged M1.1 SGGM1World class.
tree=ast.parse((SRC/"main.py").read_text(encoding="utf-8"))
world_cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="SGGM1World")
ns={"Path":pathlib.Path,"json":json,"math":math,"GAME_WIDTH":1360,"GAME_HEIGHT":780}
exec(compile(ast.Module(body=[world_cls],type_ignores=[]),"<SGGM1World M1.1>","exec"),ns)
world=ns["SGGM1World"](mp)
assert world.current_layer_id=="city_exterior" and world.can_move_to(3400,1490)
for mode,layer,x,y in [("easy","countryside",1070.0,1010.0),("normal","countryside",1070.0,1010.0),("spiffy_challenge","hellgs_inn",650.0,500.0)]:
 world.current_layer_id=layer
 assert world.can_move_to(x,y), (mode,layer,x,y,"difficulty spawn invalid")
for layer,(pid,x,y) in arrivals.items():
 assert world.can_move_to(x,y), (layer,pid,x,y,"city return arrival invalid")


shutil.copytree(DEP/"SGGM1.1",REL)
for p in list(REL.glob("SGGM1.0_*"))+list(REL.glob("SGGM1.1_*")):
 if p.is_file(): p.unlink()
for name in ["sggm1_0a.apk","sggm1_0a.tar.gz","sggm1_1.apk","sggm1_1.tar.gz"]:
 q=REL/name
 if q.exists(): q.unlink()
for p in [SRC/"main.py",SRC/"assets/main.py",REL/"main.py"]:
 s=p.read_text(encoding="utf-8").replace("SGGM1.1","SGGM1.3a")
 p.write_text(s,encoding="utf-8")
shutil.copy2(SRC/"assets/main.py",SRC/"main.py")
(REL/"m1_world_layers.json").write_text(maptext,encoding="utf-8")
s=(REL/"play.html").read_text(encoding="utf-8")
for a,b in [("SGGM1.1","SGGM1.3a"),("M1.1","M1.3a"),("sggm1_1","sggm1_3a")]: s=s.replace(a,b)
(REL/"play.html").write_text(s,encoding="utf-8")
(REL/"VERSION").write_text("M1.3a\n",encoding="utf-8")
with zipfile.ZipFile(REL/"sggm1_3a.apk","w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for n in ["main.py","m1_world_layers.json","luma_assets_e33.json"]: z.write(REL/n,n)
with tarfile.open(REL/"sggm1_3a.tar.gz","w:gz",compresslevel=9) as t:
 for n in ["main.py","m1_world_layers.json","luma_assets_e33.json"]: t.add(REL/n,arcname="assets/"+n)

log="""LUMA'S LOG — ENTRY 054
SGGM1.3a — BritRun Gets Its Bearings
Date: 17 November 2026
Baseline: SGGM1.1 exact source and complete Cloudflare site archives retrieved from GitHub main; original archives preserved unchanged.
Scope: BritRun city exterior layout, building/landmark placement, the four existing city NPC positions, city portal positions, and reciprocal city-side arrival points. No art work.

THE DESIGN
Cozmo supplied the town's essential relationships: the southeast City Gate; entry facing north into a main street; a central Market Square; the Tipsy Turnip on the north side; the Alchemy Shop to the east; a westbound street to Intersection A; Castle Path and Castle Gate to the north; and a southbound Gold District route returning to the City Gate.

M1.3a uses the existing 2:1 city sheet, walkmesh, connected road polylines, eight named landmarks, four existing NPC placeholders and portal system. It retains the simple generic building/NPC placeholder renderer. No art or drawing recipes were created or modified.

CITY ARRANGEMENT
- City Gate is on the south wall near the southeast corner. The city-side arrival is just inside the gate, facing north; the main street turns northwest toward Market Square.
- Market Square is the public centre. Kart-lotta's stand is the central placeholder; Kart-lotta stands beside it. Naz occupies the west side and Cozmo the east side.
- Tipsy Turnip faces south from the north edge of the square, with its south-side door.
- Alchemy Shop is east of the square, approached from its west/southwest side.
- The west street from the square meets Intersection A. Castle Path continues north to Castle Exterior and Castle Gate.
- The south branch from A leads into Gold District. Its east/southeast return road rejoins the City Gate, making a readable loop.
- The Little Lantern is now a small placeholder building west/left of the City Gate and immediately before the Gold District return road reaches the gate. Its existing separate interior, Grella, and three children remain unchanged.
- The map's pre-difficulty startup anchor moves from the retired west-city coordinate to (3400,1490), just inside the new southeast gate. Easy/Normal and Challenge starts remain unchanged.

CITY NPCS
The four existing city NPC IDs/roles are retained, with coordinates only repositioned: Kart-lotta (market centre), Naz (west side), Cozmo (east side), BritRun Guard (inside the gate approach). No new NPCs, dialogue, quest behavior, combat behavior, or interactions were added.

TRANSITIONS AND PRESERVATION
The 11-layer / 19-directed-portal continuous world remains. The five outgoing city portals remain the same set: Tipsy Turnip, Alchemy Shop, Castle Hall, Little Lantern, and City Gate. Only their city-side origins were moved to agree with the new doors/gate. Reciprocal city arrival coordinates on Countryside, Inn Interior, Alchemy Shop, Castle Hall, and Little Lantern were moved to corresponding safe city locations. All other non-city layer data and portal fields are unchanged.

Only city_exterior geometry/landmarks/NPC/portal positions and five incoming city target coordinates were changed in the world map. Runtime Python changes are limited to SGGM1.3a version-identification strings. The loader changes only release labels and bundle filenames to sggm1_3a while retaining M1.1 loader logic. Luma art JSON, renderer, other gameplay systems, save systems, UI, workers, D1, and every historical release remain untouched.

— Luma
"""
readme="""SGGM1.3a — BritRun City Layout (Placeholder Pass)

Baseline: exact SGGM1.1 source and complete Cloudflare site archives.

This release rearranges only BritRun's city exterior layout: connected walkmesh, road lines, building/landmark positions, the four existing city NPC positions, city portal origins, and city-side return arrivals. The Little Lantern is placed as a small placeholder building just west of the southeast City Gate and before the Gold District return road reaches the gate.

All artwork remains the existing placeholder presentation. No new art, sprite, background, image, or Luma drawing recipe was created or changed. No gameplay, NPC behavior, dialogue, quests, combat, save, interface, or worker behavior was changed. The Little Lantern interior and its existing residents/behavior remain as inherited from M1.1.

The release keeps all 11 world layers and 19 directed portals. Only the city exterior and five reciprocal incoming target positions change.
"""
tests="""SGGM1.3a — STATIC TEST RESULTS

BASELINE / INTEGRITY
- Exact M1.1 source ZIP and complete Cloudflare site ZIP retrieved from GitHub main; both passed ZIP integrity checks.
- Original M1.1 archives and historical folders were preserved unchanged.

CITY LAYOUT / STATIC VALIDATION — PASS
- World retains 11 layers and 19 directed portals.
- BritRun retains 8 named landmarks, 4 existing city NPCs, and 5 outgoing city portals.
- All 19 destination points pass a full 20x26 player-body walkmesh and blocked-area check.
- All 5 city portal origins and all 4 city NPC positions pass the same full-body check.
- Every city landmark has a safe fast-travel landing using the inherited search method.
- Every city road/doorway path centreline was sampled at 15-world-unit intervals and stayed on walkable ground.
- Main gate approach, Market Square, west street/Intersection A, Castle Path, Gold District branch/return loop, and Little Lantern approach are connected.
- The world's own initial startup anchor is now the safe new City Gate arrival at (3400,1490); the exact M1.1 SGGM1World constructor/validate method passes against the resulting map.
- Easy and Normal Stables starts and the Spiffy Challenge HELLgs start all pass the unchanged engine's can_move_to check.
- Incoming city arrivals from Countryside, Inn, Alchemy Shop, Castle Hall, and Little Lantern all land safely.
- Only city_exterior layout/landmark/NPC/portal data and those five incoming city target coordinates differ from M1.1. Remaining non-city layer data is unchanged.

PRESERVATION
- Luma art JSON is byte-identical to M1.1. No artwork or drawing recipes were modified or created.
- Main Python game logic is unchanged; only SGGM1.1 release-identification strings are relabeled SGGM1.3a.
- Pygbag loader logic is unchanged; only edition and bundle identifiers change to SGGM1.3a / sggm1_3a.
- Historical M1.1, M1.0a, M1.0, K1.12 and legacy folders remain present.
- No Worker, D1, UI, controls, save-state, quest, dialogue, NPC behavior, or combat system change.
- Python syntax compilation, inner package integrity, and release ZIP integrity pass.

LIVE TEST LIMITS
- No Pygame library is installed in the build environment; no live Pygame rendering, Pygbag compilation, or browser session was run.
"""
worker="""SGGM1.3a WORKER / GLOBAL LOG DEPLOYMENT NOTE

No Worker code, Worker route, D1 database, binding, secret, or Global Usage Log configuration was changed in SGGM1.3a. The complete Cloudflare site package retains all historical deployment folders and the existing current-site files, with SGGM1.3a added as the first/current version-catalog entry.
"""
def putdocs(base):
 for n,v in [("SGGM1.3a_LUMA_LOG_Entry054.txt",log),("SGGM1.3a_README.txt",readme),("SGGM1.3a_TEST_RESULTS.txt",tests),("SGGM1.3a_WORKER_DEPLOYMENT.txt",worker)]:
  (base/n).write_text(v,encoding="utf-8")
for b in [SRC,REL,DEP,SRC_DEP]: putdocs(b)
artsha=sha(REL/"luma_assets_e33.json")
assert artsha=="194c3acd6ce6ce55cc575d586202b5dce566aff48650e98173e05fc7ee734043"
meta={"version":"SGGM1.3a","release_name":"BritRun City Layout — Placeholder Pass","baseline":"SGGM1.1 exact GitHub source and complete Cloudflare site archives","scope":["city walkmesh and paths","city building/landmark positions","four existing city NPC positions","city portal origins","five reciprocal city arrival targets","world startup anchor moved to the new City Gate arrival"],"layers":11,"directed_portals":19,"city_landmarks":8,"city_npcs":4,"city_outgoing_portals":5,"world_start":data["start"],"placeholder_art_only":True,"artwork_modified":False,"luma_asset_json_sha256":artsha,"world_map_sha256":sha(REL/"m1_world_layers.json"),"main_py_sha256":sha(REL/"main.py"),"play_html_sha256":sha(REL/"play.html"),"worker_or_d1_changed":False,"game_logic_changed":False,"live_pygame_pygbag_or_browser_tested":False,"static_validation":"PASS"}
for b in [SRC,REL,DEP,SRC_DEP]:
 writej(b/"SGGM1.3a_BUILD_META.json",meta)
for p in [SRC/"versions.json",DEP/"versions.json",SRC_DEP/"versions.json"]:
 v=json.loads(p.read_text(encoding="utf-8"))
 for x in v["versions"]: x["current"]=False
 v["versions"].insert(0,{"version":"SGGM1.3a","title":"SGGM1.3a — BritRun City Layout (Placeholder Pass)","path":"SGGM1.3a/play.html","description":"Connected southeast City Gate, Market Square, west street/Intersection A, Castle Path, Gold District return loop, and Little Lantern west of the gate. Existing city NPCs and reciprocal arrivals are repositioned. Existing placeholder art only; no new artwork or gameplay behavior.","current":True})
 writej(p,v)
(SRC/"VERSION").write_text("M1.3a\n",encoding="utf-8")
(SRC/"m1_world_layers.json").write_text(maptext,encoding="utf-8")
(SRC_DEP/"m1_world_layers.json").write_text(maptext,encoding="utf-8")
shutil.copytree(REL,SRC_REL)
assert sha(REL/"luma_assets_e33.json")==artsha
assert (SRC/"assets/m1_world_layers.json").read_bytes()==(REL/"m1_world_layers.json").read_bytes()
assert (SRC/"assets/main.py").read_bytes()==(REL/"main.py").read_bytes()
assert (REL/"main.py").read_text().count("SGGM1.1")==0
subprocess.run([sys.executable,"-m","py_compile",str(REL/"main.py")],check=True)
shutil.rmtree(REL/"__pycache__",ignore_errors=True)
for p in [REL/"sggm1_3a.apk",REL/"sggm1_3a.tar.gz"]:
 assert p.exists()
with zipfile.ZipFile(REL/"sggm1_3a.apk") as z: assert z.testzip() is None
with tarfile.open(REL/"sggm1_3a.tar.gz","r:gz") as t:
 assert set(t.getnames())=={"assets/main.py","assets/m1_world_layers.json","assets/luma_assets_e33.json"}
for p in [REL/"SGGM1.3a_BUILD_META.json",REL/"SGGM1.3a_LUMA_LOG_Entry054.txt",REL/"SGGM1.3a_README.txt",REL/"SGGM1.3a_TEST_RESULTS.txt"]: assert p.exists()
subprocess.run(["zip","-qr","-9",str(OUT/"SGGM1.3a_SOURCE.zip"),".","-x","*.mp4","*.MP4","*/.DS_Store"],cwd=SRC,check=True)
subprocess.run(["zip","-qr","-9",str(OUT/"SGGM1.3a_COMPLETE_CLOUDFLARE_SITE.zip"),".","-x","*.mp4","*.MP4","*/.DS_Store"],cwd=DEP,check=True)
for p in [OUT/"SGGM1.3a_SOURCE.zip",OUT/"SGGM1.3a_COMPLETE_CLOUDFLARE_SITE.zip"]:
 with zipfile.ZipFile(p) as z: assert z.testzip() is None
inner_sums="".join(f"{sha(p)}  {p.name}\n" for p in [REL/"m1_world_layers.json",REL/"main.py",REL/"play.html",REL/"sggm1_3a.apk",REL/"sggm1_3a.tar.gz"])
inner_sums+=f"{artsha}  luma_assets_e33.json\n"
for b in [SRC,DEP,SRC_DEP,REL,SRC_REL]:
 (b/"SGGM1.3a_SHA256SUMS.txt").write_text(inner_sums,encoding="utf-8")
subprocess.run(["zip","-qr","-9",str(OUT/"SGGM1.3a_SOURCE.zip"),".","-x","*.mp4","*.MP4","*/.DS_Store"],cwd=SRC,check=True)
subprocess.run(["zip","-qr","-9",str(OUT/"SGGM1.3a_COMPLETE_CLOUDFLARE_SITE.zip"),".","-x","*.mp4","*.MP4","*/.DS_Store"],cwd=DEP,check=True)
for p in [OUT/"SGGM1.3a_SOURCE.zip",OUT/"SGGM1.3a_COMPLETE_CLOUDFLARE_SITE.zip"]:
 with zipfile.ZipFile(p) as z: assert z.testzip() is None
outer_sums=inner_sums+"".join(f"{sha(p)}  {p.name}\n" for p in [OUT/"SGGM1.3a_SOURCE.zip",OUT/"SGGM1.3a_COMPLETE_CLOUDFLARE_SITE.zip"])
(OUT/"SGGM1.3a_SHA256SUMS.txt").write_text(outer_sums,encoding="utf-8")
for name in ["SGGM1.3a_LUMA_LOG_Entry054.txt","SGGM1.3a_TEST_RESULTS.txt"]:
 shutil.copy2(SRC/name,OUT/name)
print(json.dumps({"status":"success","source_bytes":(OUT/"SGGM1.3a_SOURCE.zip").stat().st_size,"site_bytes":(OUT/"SGGM1.3a_COMPLETE_CLOUDFLARE_SITE.zip").stat().st_size,"art_sha256":artsha,"files":[p.name for p in OUT.iterdir()]},indent=2))
