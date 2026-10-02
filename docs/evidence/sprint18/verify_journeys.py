"""Journey verification against the REAL running local server.

Fetches each page over HTTP and reports, for each audience journey, whether the
question it exists to answer is actually answerable from what was served --
and, where a journey depends on reaching another page, that the link to it is
really present in the delivered HTML.

This records facts. It does not assert taste.
"""
import json
import re
import sys
import urllib.request

BASE = "http://127.0.0.1:8420"


def fetch(path):
    with urllib.request.urlopen(BASE + path, timeout=25) as r:
        return r.status, r.read().decode("utf-8", "replace")


def visible(html):
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.DOTALL)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.DOTALL | re.I)
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html)


def hrefs(html):
    return set(re.findall(r'href="([^"]+)"', html))


JOURNEYS = {
    "A -- recruiter / HR": {
        "page": "/",
        "must_answer": {
            "who is this": ["Karthikeyan Devadoss"],
            "what role": ["Senior Backend", "Agentic AI"],
            "why different": ["cannot approve its own writes"],
            "where is the proof": ["Evidence Index", "full evidence index"],
            "what to click next": ["View the Workbench"],
            "honest about scope": ["Current scope boundaries"],
            "separates own platform from employer": ["not an NRG product"],
        },
        "must_link_to": ["/proof", "/workbench", "/usage"],
    },
    "B -- AI / agentic hiring manager": {
        "page": "/proof",
        "must_answer": {
            "authority boundary": ["cannot approve its own writes"],
            "durability": ["survives a crash"],
            "evaluation": ["measured", "hand-labelled"],
            "security / kill switch": ["kill switch"],
            "negative result": ["failed its own test", "unproven"],
            "limits are stated": ["Limitation"],
            "status vocabulary explained": ["How to read a status"],
            "reading order offered": ["Where to start"],
        },
        "must_link_to": ["/case-study/durable-agent", "/ask-codebase", "/workbench"],
    },
    "C -- backend / architecture interviewer": {
        "page": "/proof",
        "must_answer": {
            "real java/spring system": ["Java 21", "Spring Boot"],
            "schema / database": ["migrations", "PostgreSQL"],
            "multi-service architecture": ["multi-process topology"],
            "testing evidence": ["Testcontainers", "blocking"],
            "architecture reasoning offered": ["The microservices architecture"],
        },
        "must_link_to": [
            "https://agentic-delivery-customer-app-production.up.railway.app",
            "MICROSERVICES_ARCHITECTURE.md",
            "/db/migration",
            ".github/workflows/ci.yml",
        ],
    },
}

result = {"base": BASE, "journeys": {}, "pass": True}

for name, spec in JOURNEYS.items():
    status, html = fetch(spec["page"])
    text = visible(html)
    links = hrefs(html)
    answers = {}
    for question, needles in spec["must_answer"].items():
        found = [n for n in needles if n.lower() in text.lower()]
        answers[question] = {
            "needles": needles,
            "found": found,
            "answerable": bool(found),
        }
        if not found:
            result["pass"] = False
    missing_links = []
    for href in spec["must_link_to"]:
        if not any(href in l for l in links):
            missing_links.append(href)
            result["pass"] = False
    result["journeys"][name] = {
        "page": spec["page"],
        "http_status": status,
        "answers": answers,
        "required_links_present": [l for l in spec["must_link_to"] if l not in missing_links],
        "required_links_MISSING": missing_links,
    }

print(json.dumps(result, indent=2))

print("\n" + "=" * 72)
for name, data in result["journeys"].items():
    unanswered = [q for q, a in data["answers"].items() if not a["answerable"]]
    verdict = "PASS" if not unanswered and not data["required_links_MISSING"] else "FAIL"
    print(f"{verdict}  {name}  ({data['page']}, HTTP {data['http_status']})")
    answered = len(data["answers"]) - len(unanswered)
    print(f"        {answered}/{len(data['answers'])} questions answerable from the served page")
    if unanswered:
        print(f"        UNANSWERED: {unanswered}")
    if data["required_links_MISSING"]:
        print(f"        MISSING LINKS: {data['required_links_MISSING']}")
print("=" * 72)
sys.exit(0 if result["pass"] else 1)
