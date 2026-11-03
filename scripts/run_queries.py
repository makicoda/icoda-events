"""Query claude-sonnet-4-6 for every question. Resumable: skips questions that already have a response file.
usage: python scripts/run_queries.py [--limit N] [--only GEO_LANG_prefix]"""
import json, time, sys, pathlib, argparse, datetime
import anthropic
sys.path.insert(0, str(pathlib.Path(__file__).parent)); from audit_parse import parse
ROOT = pathlib.Path(__file__).resolve().parent.parent
MODEL = "claude-sonnet-4-6"
SYSTEM = """Answer the following question as you naturally would for a real user. 
After your answer, add a section labeled SELF-AUDIT with these fields:
- POSITIONING: main framing used to describe the company
- GEOS_MENTIONED: geographies or markets referenced
- SERVICES_MENTIONED: services highlighted
- SENTIMENT: positive / neutral / negative
- CONFIDENCE: high / medium / low
- RED_FLAGS: any potentially inaccurate, outdated, or misleading claims you made"""
ap = argparse.ArgumentParser(); ap.add_argument("--limit", type=int); ap.add_argument("--only", default="")
a = ap.parse_args()
qs = [q for q in json.loads((ROOT/"queries/all_questions.json").read_text("utf-8")) if q["id"].startswith(a.only)]
if a.limit: qs = qs[:a.limit]
out = ROOT/"responses"; out.mkdir(exist_ok=True); log = ROOT/"responses/errors.log"
client = anthropic.Anthropic(); done = fail = skipped = 0
for n, q in enumerate(qs, 1):
    f = out/f"{q['id']}.json"
    if f.exists(): skipped += 1; continue
    for attempt in (1, 2):
        try:
            r = client.messages.create(model=MODEL, max_tokens=1800, system=SYSTEM,
                                       messages=[{"role":"user","content":q["question"]}])
            raw = "".join(b.text for b in r.content if b.type == "text")
            ans, audit = parse(raw)
            f.write_text(json.dumps({"id":q["id"],"geo":q["geo"],"language":q["language"],
                "question_type":q["question_type"],"question":q["question"],"answer":ans,
                "self_audit":audit,"raw":raw,"model":MODEL,"stop_reason":r.stop_reason,
                "ts":datetime.datetime.utcnow().isoformat()}, ensure_ascii=False, indent=1), "utf-8")
            done += 1; break
        except Exception as e:
            if attempt == 2:
                fail += 1
                with log.open("a", encoding="utf-8") as L: L.write(f"{q['id']}\t{type(e).__name__}: {e}\n")
            else: time.sleep(2)
    print(f"[{n}/{len(qs)}] {q['id']}  ok={done} failed={fail} skipped={skipped}", flush=True)
    time.sleep(0.5)
print(f"DONE ok={done} failed={fail} skipped={skipped}")
