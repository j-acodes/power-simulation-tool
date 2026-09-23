"""Builds the three CTO-Demo designs from the seed wizard and solves each against the running app.

Read-only by default; `--save` creates the CTO-Demo project and its three designs.
Usage: python3 build.py [--save]   (app on http://127.0.0.1:8000)
"""
import json, copy, urllib.request
B="http://127.0.0.1:8000"
def call(method, p, body=None):
    r=urllib.request.Request(B+p, json.dumps(body).encode() if body is not None else None,
                             {"Content-Type":"application/json"}, method=method)
    try: return json.load(urllib.request.urlopen(r))
    except urllib.error.HTTPError as e: raise SystemExit(f"{method} {p}: {e.code} {e.read().decode()}")
COMMON=dict(pf_target=0.95, interconnection="HV", v_hv_kv=132, export_m=0, v_mv_kv=33,
            trunk_m=800, spacing_m=350, aux_p_kw=120, aux_q_kvar=40)
BESS_PROPS={"mode":"catalogue","model":"SUNGROW_MVS7400_LS","fleet_kind":"bess","bess_solution":"sungrow-st6900ux-4h"}

def pv():
    return call("POST","/api/seed", dict(COMMON, p_poc_mw=50, station_model="SUNGROW_MVS6400",
                                        pv_inverter="sungrow-sg350hx-20", inverter_count=20))
def bess():
    # Seed the layout at 25 MW with a ~7 MW PV station, then swap every station for the BESS pairing.
    d=call("POST","/api/seed", dict(COMMON, p_poc_mw=25, station_model="SUNGROW_MVS7040",
                                    pv_inverter="sungrow-sg350hx-20", inverter_count=22))
    for n in d["nodes"]:
        if n["kind"]=="station": n["props"]=dict(BESS_PROPS)
        if n["kind"]=="busbar": n["props"]["fleet_kind"]="bess"
    # ponytail: the seed proposes 5 stations; 4 (16 containers, 110 MWh) already clear the 100 MWh gate at 98 % loading.
    d["nodes"]=[n for n in d["nodes"] if n["id"]!="s1_5"]; d["edges"]=[e for e in d["edges"] if e["target"]!="s1_5"]
    d["settings"]["tiers"]["lv_kv"]=0.69
    d["settings"]["rules"]["discharge_hours"]=4.0
    return d
def hybrid():
    d=pv(); b=bess()
    for n in d["nodes"]:
        if n["kind"]=="busbar": n["props"]["fleet_kind"]="pv"
        if n["kind"]=="poc": n["props"]["p_target_bess_mw"]=25.0
    hv=next(n["id"] for n in d["nodes"] if n["kind"]=="hv_tx")
    keep={n["id"] for n in b["nodes"] if n["kind"] in ("busbar","station")}
    ren=lambda i: "b_"+i
    # Place the BESS branch to the right of the PV circuits and aux load.
    dx=max(n["x"] for n in d["nodes"]) + 350 - min(n["x"] for n in b["nodes"] if n["id"] in keep)
    for n in b["nodes"]:
        if n["id"] in keep:
            m=copy.deepcopy(n); m["id"]=ren(n["id"]); m["x"]+=dx; d["nodes"].append(m)
    for e in b["edges"]:
        if e["source"] in keep and e["target"] in keep:
            m=copy.deepcopy(e); m["id"]=ren(e["id"]); m["source"]=ren(e["source"]); m["target"]=ren(e["target"]); d["edges"].append(m)
        elif e["target"] in keep and e["source"]==hv:
            m=copy.deepcopy(e); m["id"]=ren(e["id"]); m["target"]=ren(e["target"]); d["edges"].append(m)
    d["settings"]["rules"]["discharge_hours"]=4.0
    return d
DESIGNS={"PV 50 MW":("pv",pv),"BESS 25 MW / 100 MWh":("bess",bess),"Hybrid PV 50 MW + BESS 25 MW":("hybrid",hybrid)}
if __name__=="__main__":
    import sys
    out={}
    for name,(tech,f) in DESIGNS.items():
        d=f(); s=call("POST","/api/solve",d)
        sm=(s["results"] or {}).get("summary",{})
        print(name, "issues:", [(i["code"],i["message"][:120]) for i in s["issues"]],
              "stations:", sm.get("n_stations"), "loss%:", sm.get("loss_percent_of_p_inv"))
        out[name]=(tech,d)
    if "--update-hybrid" in sys.argv:
        cur=call("GET",f"/api/designs/{sys.argv[-1]}")
        r=call("PUT",f"/api/designs/{cur['id']}",{"payload":out["Hybrid PV 50 MW + BESS 25 MW"][1],"version":cur["version"],"last_edited_by":"Javier"})
        print("updated", r["id"], "v", r["version"])
    if "--save" in sys.argv:
        assert not any(p["name"]=="CTO-Demo" for p in call("GET","/api/projects")), "CTO-Demo already exists"
        pid=call("POST","/api/projects",{"name":"CTO-Demo"})["id"]
        for name,(tech,d) in out.items():
            r=call("POST",f"/api/projects/{pid}/designs",{"name":name,"technology":tech,"payload":d,"last_edited_by":"Javier"})
            print("saved design", r["id"], name)
        print("project", pid)
