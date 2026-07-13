import argparse, hashlib, html, json, os, re
from pathlib import Path
import requests

ROOT=Path(__file__).parent
HARDWARE={"analog":9,"mixed-signal":9,"mixed signal":9,"asic":9,"fpga":9,"rtl":9,"silicon":8,"circuit":8,"hardware":8,"electrical":8,"verification":7,"validation":7,"embedded":7,"firmware":7,"architecture":7,"physical design":8,"signal integrity":8,"power integrity":8,"rf":8,"pcb":7,"semiconductor":7,"process engineer":6,"test engineer":5,"packaging":6,"robotics":4}
METROS=("san francisco","bay area","san jose","santa clara","sunnyvale","mountain view","austin","boston","cambridge","new york","seattle","los angeles","san diego","denver","phoenix","chicago","dallas","raleigh","durham","washington","arlington","irvine","baltimore","philadelphia","pittsburgh")
EXCLUDE=("senior","staff","principal","manager","director","full time","full-time")

def greenhouse(company, token):
    r=requests.get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true",timeout=30); r.raise_for_status()
    return [{"company":company,"title":x["title"],"location":x.get("location",{}).get("name","Unknown"),"url":x["absolute_url"],"description":re.sub("<[^>]+>"," ",x.get("content",""))} for x in r.json().get("jobs",[])]

def lever(company, token):
    r=requests.get(f"https://api.lever.co/v0/postings/{token}?mode=json",timeout=30); r.raise_for_status()
    return [{"company":company,"title":x["text"],"location":x.get("categories",{}).get("location","Unknown"),"url":x["hostedUrl"],"description":x.get("descriptionPlain","")} for x in r.json()]

def key(job):
    return hashlib.sha256("|".join(str(job[x]) for x in ("company","title","location","url")).lower().encode()).hexdigest()[:20]

def rank(job):
    text=(job["title"]+" "+job["description"]).lower(); title=job["title"].lower()
    points=12 if "intern" in title else 0; reasons=["intern"] if "intern" in title else []
    for term,value in HARDWARE.items():
        if term in text: points+=value; reasons.append(term)
    if any(x in title for x in EXCLUDE): points-=30
    if any(x in job["location"].lower() for x in METROS): points+=3; reasons.append("major metro")
    return points,list(dict.fromkeys(reasons))[:5]

def match(job):
    text=(job["title"]+" "+job["description"]).lower()
    title=job["title"].lower()
    wrong_term=any(x in title for x in ("fall","spring","winter","co-op","coop"))
    wrong_year=any(str(y) in title for y in range(2024,2031) if y != 2027)
    intern_title=bool(re.search(r"\bintern(?:ship)?\b",title))
    hardware_title=any(x in title for x in HARDWARE)
    return intern_title and hardware_title and not wrong_term and not wrong_year and not any(x in title for x in EXCLUDE)

def notify_github(subject, body):
    token=os.environ.get("GITHUB_TOKEN")
    repository=os.environ.get("GITHUB_REPOSITORY")
    if not token or not repository: raise RuntimeError("GitHub Actions environment is missing")
    r=requests.post(f"https://api.github.com/repos/{repository}/issues",headers={"authorization":f"Bearer {token}","accept":"application/vnd.github+json"},json={"title":subject,"body":body,"assignees":["saul-castillo"]},timeout=30)
    r.raise_for_status()

def run(dry=False,test=False):
    config=json.loads((ROOT/"config.json").read_text())
    if test:
        notify_github("JTracker test: notifications are working","JTracker is connected. GitHub should email this assigned issue to your configured notification address."); return
    jobs=[]; failures=[]
    for company,kind,token in config["sources"]:
        try: jobs += (greenhouse if kind=="greenhouse" else lever)(company,token)
        except Exception as e: failures.append(f"{company}: {e}")
    ranked=sorted([(rank(j)[0],rank(j)[1],j) for j in jobs if match(j)],reverse=True,key=lambda x:x[0])
    state_path=ROOT/"data/seen.json"; seen=set(json.loads(state_path.read_text())["seen"])
    new=[x for x in ranked if key(x[2]) not in seen]
    print(json.dumps({"fetched":len(jobs),"matches":len(ranked),"new":len(new),"failures":failures},indent=2))
    if dry:
        for points,_,job in new[:20]: print(points,job["company"],job["title"],job["location"])
        return
    if new:
        rows="\n".join(f'- **[{j["title"]}]({j["url"]})** — {j["company"]}, {j["location"]} — score {p} ({", ".join(r)})' for p,r,j in new)
        notify_github(f'JTracker: {len(new)} new hardware internship match(es)',"## New hardware internship matches\n\n"+rows)
    state_path.write_text(json.dumps({"seen":sorted(seen|{key(x[2]) for x in ranked})},indent=2)+"\n")
    if failures and not jobs: raise RuntimeError("All sources failed")

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--dry-run",action="store_true"); p.add_argument("--test-email",action="store_true"); a=p.parse_args(); run(a.dry_run,a.test_email)
