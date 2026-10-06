"""Builds agent/web/recruiters.json, the data behind the /recruiters page.

Inputs (all in the repository):
  - agent/recruiters_source.yaml: hand-written, reviewed profile facts,
    posting list, requirement themes with verbatim posting quotes, evidence
    links and honest limits.
  - agent/web/eval-results.json, triage-evidence.json,
    ask-codebase-examples.json: the published snapshots. Numbers on the page
    come from these files, never from typing them into the page.
  - agent/web/case-study-durable-agent.html: the case-study banner figures.

The build refuses to write the output if any evidence link is broken:
  - an internal route must be served by web_server.py on this tree. It is
    "live" when origin/master also serves it, otherwise "pending_deploy" and
    the page falls back to the page's source file on this branch;
  - an anchor (#id) must exist in the page the route serves;
  - a repository link (github.com/.../blob/master/<path>) must exist on
    origin/master, otherwise on this tree (then it is rewritten to this
    branch and marked pending);
  - anything else must be an absolute https URL.
--check-online additionally fetches every external URL once and records the
HTTP status (GET only; the page routes, GitHub and the postings, never an
API endpoint). --posting-text-dir DIR verifies every quote is a verbatim
excerpt of the posting text captured on the access date.

Usage (commit code first, then generate on a clean tree):
    python publish_recruiters_page.py [--check-online] [--posting-text-dir DIR] [--stdout]
"""
import hashlib
import html as html_lib
import inspect
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yaml

AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parent
WEB_DIR = AGENT_DIR / "web"
SOURCE_PATH = AGENT_DIR / "recruiters_source.yaml"
OUTPUT_PATH = WEB_DIR / "recruiters.json"
CASE_STUDY_PATH = WEB_DIR / "case-study-durable-agent.html"
SNAPSHOTS = {
    "eval": WEB_DIR / "eval-results.json",
    "triage": WEB_DIR / "triage-evidence.json",
    "ask": WEB_DIR / "ask-codebase-examples.json",
}
REPO_URL = "https://github.com/karthikdevadoss/agentic-software-delivery"
MASTER_BLOB = REPO_URL + "/blob/master/"
LIVE_BASE = "https://agentic-platform-backend-production.up.railway.app"
MASTER_REF = "origin/master"

HASHED_INPUTS = [SOURCE_PATH, CASE_STUDY_PATH, *SNAPSHOTS.values()]


class LinkError(ValueError):
    pass


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_lf(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def compute_input_hashes(paths=None) -> dict:
    paths = HASHED_INPUTS if paths is None else paths
    return {p.relative_to(REPO_ROOT).as_posix(): _sha256_text(_read_lf(p)) for p in paths}


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=check)


# --------------------------------------------------------------- routes

ROUTE_RE = re.compile(r'Route\(\s*"(/[^"{]*)"')


def routes_in_source(source: str) -> set:
    return set(ROUTE_RE.findall(source))


def served_routes() -> dict:
    """Exact path -> the HTML file name its handler serves (or None)."""
    import web_server
    out = {}
    for route in web_server.routes:
        path = getattr(route, "path", None)
        if not path or "{" in path:
            continue
        page = None
        endpoint = getattr(route, "endpoint", None)
        try:
            m = re.search(r'WEB_DIR\s*/\s*"([^"]+\.html)"', inspect.getsource(endpoint))
            page = m.group(1) if m else None
        except (TypeError, OSError):
            page = None
        out[path] = page
    return out


def production_routes() -> set:
    """Routes origin/master serves. Master is what gets deployed; a route that
    exists only on this branch is pending deploy."""
    res = _git("show", f"{MASTER_REF}:agent/web_server.py", check=False)
    if res.returncode != 0:
        raise LinkError(f"cannot read {MASTER_REF}:agent/web_server.py ({res.stderr.strip()})")
    return routes_in_source(res.stdout)


def _exists_at(ref: str, rel: str) -> bool:
    return _git("cat-file", "-e", f"{ref}:{rel}", check=False).returncode == 0


def current_branch() -> str:
    return _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def classify_link(url: str, *, served: dict, production: set, branch: str,
                  exists_on_master=None, exists_on_head=None) -> dict:
    """Returns the rendered link record or raises LinkError."""
    exists_on_master = exists_on_master or (lambda rel: _exists_at(MASTER_REF, rel))
    exists_on_head = exists_on_head or (lambda rel: _exists_at("HEAD", rel))
    if url.startswith("/"):
        path, _, anchor = url.partition("#")
        if path not in served:
            raise LinkError(f"{url}: no route serves {path}")
        page = served[path]
        if anchor:
            if not page:
                raise LinkError(f"{url}: cannot locate the page for anchor #{anchor}")
            page_html = (WEB_DIR / page).read_text(encoding="utf-8")
            if not re.search(r'id="' + re.escape(anchor) + r'"', page_html):
                raise LinkError(f"{url}: {page} has no element with id={anchor!r}")
        if path in production:
            return {"url": url, "status": "live"}
        if not page:
            raise LinkError(f"{url}: pending deploy and no source page to fall back to")
        fallback = f"{REPO_URL}/blob/{branch}/agent/web/{page}"
        return {"url": url, "status": "pending_deploy", "fallback_url": fallback}
    if url.startswith(MASTER_BLOB):
        rel = url[len(MASTER_BLOB):]
        if exists_on_master(rel):
            return {"url": url, "status": "source"}
        if exists_on_head(rel):
            return {"url": f"{REPO_URL}/blob/{branch}/{rel}", "status": "source_pending"}
        raise LinkError(f"{url}: {rel} is not in the repository")
    if url.startswith("https://"):
        return {"url": url, "status": "external"}
    raise LinkError(f"{url}: not an internal route, repository file or https URL")


# --------------------------------------------------------------- metrics

def eval_metrics(snap: dict) -> dict:
    gate = (snap.get("ci_gate") or {}).get("observed") or {}
    latest = gate.get("latest_run") or {}
    decision = snap.get("agent_decision") or {}
    return {
        "generated_at": snap["generated_at"],
        "commit_sha": snap["commit_sha"],
        "overall_passed": snap["overall_passed"],
        "labelled_set": snap.get("labelled_set"),
        "metrics": [{k: m[k] for k in ("key", "label", "score", "threshold", "comparator", "passed")}
                    for m in snap["metrics"]],
        "ci_eval_step_on_master": {
            "observed_at": gate.get("observed_at"),
            "latest_status": latest.get("eval_step"),
            "last_success_at": (gate.get("last_eval_step_success") or {}).get("created_at"),
        },
        "agent_decision": {
            "label": decision.get("label"),
            "passed": (decision.get("summary") or {}).get("PASS"),
            "total": decision.get("cases_total"),
        } if decision else None,
    }


def triage_metrics(snap: dict) -> dict:
    total = failed = skipped = skipped_needing_docker = 0
    for scenario in snap["scenarios"]:
        for t in scenario.get("java_integration_tests") or []:
            r = t.get("result") or {}
            total += r.get("tests", 0)
            failed += r.get("failures", 0) + r.get("errors", 0)
            skipped += r.get("skipped", 0)
            if t.get("needs_docker"):
                skipped_needing_docker += r.get("skipped", 0)
    return {
        "generated_at": snap["generated_at"],
        "commit_sha": snap["commit_sha"],
        "scenarios": len(snap["scenarios"]),
        "java_tests": total, "java_passed": total - failed - skipped,
        "java_failed": failed, "java_skipped": skipped,
        "skip_reason": ("needs Docker, which the recording machine did not have"
                        if skipped and skipped == skipped_needing_docker else None),
    }


def ask_metrics(snap: dict) -> dict:
    statuses = [e.get("status") for e in snap["examples"]]
    return {
        "generated_at": snap["generated_at"],
        "commit_sha": snap["commit_sha"],
        "examples": len(statuses),
        "strong_evidence": statuses.count("STRONG_EVIDENCE"),
        "llm_calls": snap.get("llm_calls"),
    }


BANNER_RE = re.compile(r"<dt>(.*?)</dt>\s*<dd>(.*?)<small>(.*?)</small></dd>", re.S)


def case_study_metrics(page_html: str) -> dict:
    banner = re.search(r'<dl class="banner">(.*?)</dl>', page_html, re.S)
    if not banner:
        raise ValueError("case study banner not found")
    items = [{"label": html_lib.unescape(a).strip(), "value": html_lib.unescape(b).strip(),
              "note": html_lib.unescape(c).strip()} for a, b, c in BANNER_RE.findall(banner.group(1))]
    if len(items) != 3:
        raise ValueError(f"expected 3 banner items, found {len(items)}")
    return {"banner": items}


# --------------------------------------------------------------- quotes

def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(text).replace("\xa0", " ")).strip().lower()


def iter_quotes(source: dict):
    for section in list(source["requirements"]) + list(source["gaps"]):
        for pid, quote in section["asked_by"].items():
            yield section.get("id") or section["title"], pid, quote


def verify_quotes(source: dict, text_dir: Path) -> int:
    texts = {p.stem: _norm(p.read_text(encoding="utf-8")) for p in Path(text_dir).glob("*.txt")}
    missing = [(s, pid) for s, pid, q in iter_quotes(source) if _norm(q) not in texts.get(pid, "")]
    if missing:
        raise ValueError(f"quotes not found verbatim in captured posting text: {missing}")
    return sum(1 for _ in iter_quotes(source))


# --------------------------------------------------------------- build

def validate_source(source: dict) -> None:
    ids = [p["id"] for p in source["postings"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate posting id")
    for section, pid, quote in iter_quotes(source):
        if pid not in ids:
            raise ValueError(f"{section}: unknown posting id {pid!r}")
        if not quote.strip():
            raise ValueError(f"{section}: empty quote for {pid}")


def build_page_data(source: dict, *, snapshots: dict, case_study_html: str, served: dict,
                    production: set, branch: str, commit_sha: str, generated_at: str,
                    working_tree_dirty: bool, inputs: dict, quotes_verified=None,
                    link_check_online=None, exists_on_master=None, exists_on_head=None) -> dict:
    validate_source(source)
    metrics = {
        "eval": eval_metrics(snapshots["eval"]),
        "triage": triage_metrics(snapshots["triage"]),
        "ask": ask_metrics(snapshots["ask"]),
        "case_study": case_study_metrics(case_study_html),
    }
    total_postings = len(source["postings"])

    def link(url):
        return classify_link(url, served=served, production=production, branch=branch,
                             exists_on_master=exists_on_master, exists_on_head=exists_on_head)

    def asked(section):
        return [{"posting": pid, "quote": q} for pid, q in section["asked_by"].items()]

    requirements = []
    for r in source["requirements"]:
        evidence = []
        for e in r["evidence"]:
            item = {"label": e["label"], **link(e["url"])}
            if e.get("metrics"):
                item["metrics"] = e["metrics"]
            evidence.append(item)
        requirements.append({"id": r["id"], "title": r["title"], "asked_count": len(r["asked_by"]),
                             "asked_by": asked(r), "evidence": evidence,
                             "limits": " ".join(r["limits"].split())})
    gaps = [{"title": g["title"], "detail": g["detail"], "asked_count": len(g["asked_by"]),
             "asked_by": asked(g)} for g in source["gaps"]]
    profile = dict(source["profile"])
    profile["nrg"] = " ".join(profile["nrg"].split())
    profile["links"] = [{"label": l["label"], **link(l["url"])} for l in profile["links"]]
    postings = [{**p, **link(p["url"])} for p in source["postings"]]
    headline = [
        {"metric": "eval", "link": link("/eval")},
        {"metric": "case_study", "link": link("/case-study/durable-agent")},
        {"metric": "triage", "link": link("/triage/evidence")},
    ]
    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "commit_sha": commit_sha,
        "branch": branch,
        "working_tree_dirty": working_tree_dirty,
        "postings_accessed": str(source["postings_accessed"]),
        "postings_note": " ".join(source["postings_note"].split()),
        "postings_total": total_postings,
        "profile": profile,
        "headline": headline,
        "metrics": metrics,
        "requirements": requirements,
        "gaps": gaps,
        "postings": postings,
        "link_check": {"offline": "passed", "online": link_check_online},
        "quotes_verified": quotes_verified,
        "inputs": inputs,
    }


def collect_urls(data: dict) -> list:
    urls = []
    for p in data["postings"]:
        urls.append(p["url"])
    for l in data["profile"]["links"]:
        urls.append(l["url"])
    for r in data["requirements"]:
        for e in r["evidence"]:
            urls.append(e["url"])
            if e.get("fallback_url"):
                urls.append(e["fallback_url"])
    seen, out = set(), []
    for u in urls:
        full = LIVE_BASE + u if u.startswith("/") else u
        if full not in seen:
            seen.add(full)
            out.append(full)
    return out


def check_online(urls: list, timeout: int = 20) -> dict:
    results = []
    for url in urls:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (recruiters-page link check)"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = resp.status
        except urllib.error.HTTPError as e:
            status = e.code
        except (urllib.error.URLError, OSError) as e:
            status = f"error: {type(e).__name__}"
        results.append({"url": url, "status": status})
    checked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {"checked_at": checked_at, "results": results}


def main(argv: list) -> int:
    source = yaml.safe_load(SOURCE_PATH.read_text(encoding="utf-8"))
    snapshots = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in SNAPSHOTS.items()}
    out_rel = OUTPUT_PATH.relative_to(REPO_ROOT).as_posix()
    dirty = any(l.strip() and not l.endswith(out_rel)
                for l in _git("status", "--porcelain").stdout.splitlines())
    inputs = compute_input_hashes()
    quotes_verified = None
    if "--posting-text-dir" in argv:
        text_dir = Path(argv[argv.index("--posting-text-dir") + 1])
        n = verify_quotes(source, text_dir)
        quotes_verified = {"quotes": n, "against": f"posting text captured on {source['postings_accessed']}",
                           "source_sha256": inputs[SOURCE_PATH.relative_to(REPO_ROOT).as_posix()]}
    elif OUTPUT_PATH.exists():
        previous = json.loads(OUTPUT_PATH.read_text(encoding="utf-8")).get("quotes_verified")
        if previous and previous.get("source_sha256") == inputs[SOURCE_PATH.relative_to(REPO_ROOT).as_posix()]:
            quotes_verified = previous
    data = build_page_data(
        source, snapshots=snapshots, case_study_html=CASE_STUDY_PATH.read_text(encoding="utf-8"),
        served=served_routes(), production=production_routes(), branch=current_branch(),
        commit_sha=_git("rev-parse", "HEAD").stdout.strip(),
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        working_tree_dirty=dirty, inputs=inputs, quotes_verified=quotes_verified)
    if "--check-online" in argv:
        online = check_online(collect_urls(data))
        broken = [r for r in online["results"] if r["status"] in (404, 410)
                  and not (r["url"].startswith(LIVE_BASE) and _is_pending(data, r["url"]))]
        data["link_check"]["online"] = online
        if broken:
            raise LinkError(f"online check found broken links: {broken}")
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if "--stdout" in argv:
        print(text, end="")
    else:
        OUTPUT_PATH.write_text(text, encoding="utf-8")
        print(f"wrote {out_rel} (commit={data['commit_sha'][:7]}, branch={data['branch']}, "
              f"requirements={len(data['requirements'])}, gaps={len(data['gaps'])}, "
              f"quotes_verified={'yes' if quotes_verified else 'no'})")
    return 0


def _is_pending(data: dict, full_url: str) -> bool:
    path = full_url[len(LIVE_BASE):]
    for r in data["requirements"]:
        for e in r["evidence"]:
            if e["url"] == path and e["status"] == "pending_deploy":
                return True
    return any(h["link"]["url"] == path and h["link"]["status"] == "pending_deploy" for h in data["headline"])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
