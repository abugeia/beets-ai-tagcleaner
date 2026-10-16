import json, time, urllib.request, urllib.error, sys, os
# Plugin under test: /s/aitagcleaner.py (local copy) if mounted, else the one in the image.
sys.path.insert(0, "/s")
try:
    from aitagcleaner import DEFAULT_PROMPT, build_prompt
except ImportError:
    from beetsplug.aitagcleaner import DEFAULT_PROMPT, build_prompt
URL="http://ollama-cpu.ai:11434"
MODELS=os.environ.get("MODELS","gemma3:4b").split(",")
cases=json.load(open("/s/cases.json"))
# v1 = historical tags-only prompt, kept as a baseline.
V1=("You clean music metadata coming from YouTube/streaming downloads. "
    "Given a raw artist and title, return the real performing artist and the "
    "clean song title. Remove decorations such as (Official Video), "
    "(Official Audio), (Lyric Video), (Visualizer), [ ... ] brackets, "
    "'Remaster'/'Remastered' + year, and channel names; move any 'feat.'/'ft.' "
    "credit OUT of the title. Keep the original accents and diacritics. "
    "Never invent information. Reply ONLY with compact JSON: "
    '{"artist": "...", "title": "..."}.')
def post(path,payload,timeout=300):
    r=urllib.request.Request(URL+path,data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(r,timeout=timeout) as resp: return json.load(resp)
def gen(model,prompt):
    p={"model":model,"prompt":prompt,"stream":False,"format":"json","options":{"temperature":0},"think":False,"keep_alive":"10m"}
    try: return post("/api/generate",p)
    except urllib.error.HTTPError as e:
        if e.code==400: p.pop("think"); return post("/api/generate",p)
        raise
def unload_all():
    try:
        for m in json.load(urllib.request.urlopen(URL+"/api/ps"))["models"]:
            post("/api/generate",{"model":m["name"],"keep_alive":0},60)
    except Exception as e: print(json.dumps({"warn":"unload "+str(e)}),flush=True)
for model in MODELS:
    unload_all()
    try: gen(model,"Reply with JSON {\"ok\": true}")
    except Exception as e:
        print(json.dumps({"model":model,"fatal":str(e)}),flush=True); continue
    for pv in os.environ.get("PROMPTS","v2").split(","):
        for i,c in enumerate(cases):
            if pv=="v1": prompt="%s\nRaw: artist=%r title=%r"%(V1,c["a"],c["t"])
            else: prompt=build_prompt(DEFAULT_PROMPT,c["a"],c["t"],c["f"])
            t0=time.time()
            try:
                r=gen(model,prompt); out=json.loads(r["response"]); err=None
            except Exception as e: out=None; err=str(e)[:200]
            print(json.dumps({"model":model,"pv":pv,"i":i,"out":out,"err":err,"dt":round(time.time()-t0,2)},ensure_ascii=False),flush=True)
unload_all()
