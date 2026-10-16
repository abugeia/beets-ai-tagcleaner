import json, re, sys, unicodedata, collections
S=sys.argv[1]
cases=json.load(open(S+"/cases.json"))
def n(s):
    s=unicodedata.normalize("NFC",str(s or "")).casefold()
    s=s.replace("’","'").replace("‘","'").replace("‐","-").replace("–","-")
    return re.sub(r"\s+"," ",s).strip(" \"'")
def main_artist(s): return re.split(r"\s+(?:feat\.?|ft\.?|featuring)\s+",n(s))[0]
res=collections.defaultdict(lambda: collections.defaultdict(lambda:[0,0])); lat=collections.defaultdict(list); fails=collections.defaultdict(list)
for line in open(S+"/results.jsonl"):
    r=json.loads(line)
    if "pv" not in r:
        if "fatal" in r: print("FATAL",r["model"],r["fatal"][:150]); 
        continue
    c=cases[r["i"]]; o=r["out"] or {}; k=(r["model"],r["pv"]); lat[k].append(r["dt"])
    a,t=o.get("artist",""),o.get("title","")
    if c["cat"]=="clean": ok= n(a)==n(c["a"]) and n(t)==n(c["t"])
    else: ok= main_artist(a) in [n(x) for x in c["ea"]] and n(t) in [n(x) for x in c["et"]]
    res[k][c["cat"]][1]+=1; res[k][c["cat"]][0]+=ok; res[k]["TOTAL"][1]+=1; res[k]["TOTAL"][0]+=ok
    if not ok: fails[k].append(f'  [{c["cat"]}] {c["a"]!r}/{c["t"]!r} -> {a!r}/{t!r}' + (f' ERR {r["err"][:60]}' if r["err"] else ""))
cats=["clean","deco","swap","soundcloud","empty","TOTAL"]
print(f'{"model":14}{"pv":4}'+"".join(f"{c:>12}" for c in cats)+f'{"s/titre":>9}')
for k in sorted(res):
    print(f"{k[0]:14}{k[1]:4}"+"".join(f'{"%d/%d"%tuple(res[k][c]):>12}' for c in cats)+f"{sum(lat[k])/len(lat[k]):>9.2f}")
if len(sys.argv)>2:
    for k in sorted(fails):
        if k[1]=="v2": print("\n==",k); print("\n".join(fails[k]))
