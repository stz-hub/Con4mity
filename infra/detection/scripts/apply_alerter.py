import glob, os, yaml
ACTIVE = "infra/detection/elastalert2/rules/active"
SIGMA  = "infra/detection/sigma-library"
levelmap = {}
for f in glob.glob(SIGMA + "/**/*.yml", recursive=True):
    try: d = yaml.safe_load(open(f))
    except Exception: d = None
    if isinstance(d, dict):
        levelmap[os.path.basename(f)] = str(d.get("level","")).lower()
sevmap = {"critical":"critical","high":"high","medium":"medium","low":"low","informational":"low","info":"low"}
n=0
for f in sorted(glob.glob(ACTIVE + "/*.yml")):
    r = yaml.safe_load(open(f))
    if not isinstance(r, dict): 
        print("SKIP(non-dict)", os.path.basename(f)); continue
    sev = sevmap.get(levelmap.get(os.path.basename(f),""), "medium")
    r["index"] = "con4mity-logs-*"
    r["timestamp_field"] = "@timestamp"
    r["alert"] = ["post"]
    r["http_post_url"] = "http://__DASHBOARD__/api/webhook/alert"
    r["http_post_headers"] = {"X-Webhook-Token": "__TOKEN__", "Content-Type": "application/json"}
    r["http_post_static_payload"] = {"rule_name": r.get("name", os.path.basename(f)), "severity": sev}
    r["http_post_payload"] = {"host": "host"}
    r.setdefault("realert", {"minutes": 1})
    yaml.safe_dump(r, open(f,"w"), default_flow_style=False, allow_unicode=True, sort_keys=False)
    n+=1
print("injecte dans", n, "regles")
