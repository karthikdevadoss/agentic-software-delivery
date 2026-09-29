"""
JD Match eval runner (Sprint 13, BL-098). Runs agent/evals/jd_match_dataset.json
once against the REAL model and embedder, scores DETERMINISTICALLY, writes
agent/evals/jd_match_results.json (committed, failures included), exit 0 only
if every case holds.

    python agent/jd_match_eval.py            # real calls (~2 per matched case)
    python agent/jd_match_eval.py --results  # print the last committed results

Deterministic checks per case:
  * the status is the expected one;
  * zero invented ids: every capability id in the result is in the registry
    AND in that requirement's code-built shortlist;
  * known-absent capabilities never DEMONSTRATED: any requirement whose text
    contains a known-absent term is not DEMONSTRATED;
  * every evidence link on the page is exactly the registry's link list;
  * the injection case reports injection_detected and no requirement is
    DEMONSTRATED without a valid registry id;
  * at least min_requirements were extracted, so the extraction step is real.
"""
import json
import pathlib
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

DATASET = HERE / "evals" / "jd_match_dataset.json"
RESULTS = HERE / "evals" / "jd_match_results.json"


def score(case: dict, out: dict, registry: dict, absent_terms: list[str]) -> list[str]:
    bad = []
    if out.get("status") != case["expect"]:
        bad.append(f"status {out.get('status')} != {case['expect']}")
        return bad
    if case["expect"] != "MATCHED":
        return bad
    reqs = out.get("requirements") or []
    if len(reqs) < case.get("min_requirements", 1):
        bad.append(f"only {len(reqs)} requirements extracted (< {case.get('min_requirements')})")
    short = out.get("shortlist") or {}
    for r in reqs:
        for c in r.get("capabilities") or []:
            if c["id"] not in registry:
                bad.append(f"{r['id']}: INVENTED id {c['id']}")
            elif c["id"] not in (short.get(r["id"]) or []):
                bad.append(f"{r['id']}: id {c['id']} outside its shortlist")
            if c.get("evidence_links") != registry[c["id"]].get("evidence_links") if c["id"] in registry else False:
                bad.append(f"{r['id']}: evidence links not the registry's")
        if r["status"] != "NOT_DEMONSTRATED" and not r.get("capabilities"):
            bad.append(f"{r['id']}: {r['status']} without evidence")
        text = r["text"].lower()
        terms = [t for t in (case.get("must_not_demonstrate_terms") or absent_terms) if t in text]
        if terms and r["status"] == "DEMONSTRATED":
            bad.append(f"{r['id']}: DEMONSTRATED although it asks for {terms}")
    if case.get("expect_injection_detected") and not out.get("injection_detected"):
        bad.append("injection not detected")
    return bad


def run() -> int:
    import jd_match as jm
    import showcase_data
    registry = showcase_data.load_capability_registry()
    ds = json.loads(DATASET.read_text(encoding="utf-8"))
    results = {"ran_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cases": [], "all_held": True,
               "model_calls": 0, "cost_usd": 0.0, "cost_known": True}
    for case in ds["cases"]:
        jm.reset_budgets_for_tests()
        t0 = time.time()
        out = jm.match(case["jd"], skip_budgets=True)
        bad = score(case, out, registry, ds["_known_absent_terms"])
        model = out.get("model") or {}
        results["model_calls"] += int(model.get("calls") or 0)
        if model.get("calls"):
            if model.get("cost_known"):
                results["cost_usd"] += float(model.get("cost_usd") or 0)
            else:
                results["cost_known"] = False
        row = {"id": case["id"], "expect": case["expect"], "status": out.get("status"),
               "summary": out.get("summary"), "injection_detected": out.get("injection_detected"),
               "redacted_reasons": out.get("redacted_reasons"), "dropped_ids": out.get("dropped_ids"),
               "downgrades": out.get("downgrades"), "elapsed_seconds": round(time.time() - t0, 1),
               "requirements": [{"text": r["text"], "status": r["status"],
                                 "capability_ids": [c["id"] for c in r.get("capabilities") or []],
                                 "reason": r["reason"]} for r in out.get("requirements") or []],
               "failures": bad, "held": not bad}
        results["cases"].append(row)
        results["all_held"] = results["all_held"] and not bad
        print(f"[{'PASS' if not bad else 'FAIL'}] {case['id']:26} status={out.get('status'):24} "
              f"reqs={len(out.get('requirements') or [])} summary={out.get('summary')}")
        for b in bad:
            print("       -", b)
    results["cost_usd"] = round(results["cost_usd"], 4)
    RESULTS.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nJD MATCH EVAL {'PASSED' if results['all_held'] else 'FAILED'} -- "
          f"{sum(1 for c in results['cases'] if c['held'])}/{len(results['cases'])} cases, "
          f"{results['model_calls']} model calls, cost_usd={results['cost_usd']} (known={results['cost_known']})")
    print("results:", RESULTS)
    return 0 if results["all_held"] else 1


if __name__ == "__main__":
    if "--results" in sys.argv:
        print(RESULTS.read_text(encoding="utf-8")); sys.exit(0)
    sys.exit(run())
