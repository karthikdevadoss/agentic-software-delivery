#!/usr/bin/env bash
# Deploy the platform backend WITH the Standing Interview corpus.
#
# WHY THIS SCRIPT EXISTS
# The corpus is built from the private knowledge base and must never enter this
# public repository, but the deployed container needs it or Standing Interview
# cannot answer.
#
# THE MECHANISM, CORRECTED 2026-09-27 (Sprint 10)
# `railway up` uploads the local working directory AND RESPECTS .gitignore. An
# earlier version of this header claimed the opposite -- inferred from
# deploy_customer_app.sh's note that the upload "does not include the .git
# folder", which is a statement about .git, not about ignored files. Two real
# deploys shipped an empty corpus before that was established, and a
# .railwayignore did not override it either. So the corpus is deliberately
# UNTRACKED BUT NOT IGNORED:
#   * not ignored  -> `railway up` uploads it, so the container can answer
#   * not tracked  -> no book text ever lands in this public repository
# That combination is load-bearing and fragile in both directions, so both
# halves are asserted below and in agent/test_standing_interview.py. Never run
# `git add -A` in this repository.
#
# The ordering matters and is the reason this is a script rather than two
# commands in a runbook: build the corpus FIRST, assert every invariant, run the
# real acceptance gate against the real corpus, and only then deploy. Deploying
# without the corpus produces a page that loads and cannot answer, which is
# worse than no page -- and the nav entry self-hides in exactly that case, so
# the failure would otherwise be quiet.
#
# Run:  ./scripts/deploy_platform_with_si_corpus.sh
#       ./scripts/deploy_platform_with_si_corpus.sh --skip-build   # corpus is current
set -euo pipefail

cd "$(dirname "$0")/.."
CORPUS="agent/.si_corpus/corpus.json"
HOST="https://agentic-platform-backend-production.up.railway.app"
SKIP_BUILD="${1:-}"

if [[ "$SKIP_BUILD" == "--skip-build" && -s "$CORPUS" ]]; then
  echo "==> Reusing the existing corpus (--skip-build)"
else
  echo "==> Building the Standing Interview corpus from the private knowledge base"
  python scripts/build_si_corpus.py
fi

if [[ ! -s "$CORPUS" ]]; then
  echo "ABORT: $CORPUS is missing or empty. Refusing to deploy a page that cannot answer." >&2
  exit 1
fi

# Half one: NOT ignored, or the upload silently drops it and the page ships empty.
if git check-ignore -q "$CORPUS"; then
  echo "ABORT: $CORPUS IS gitignored, so 'railway up' will not upload it and the" >&2
  echo "       deployed page will load with zero chunks. Remove the ignore rule." >&2
  exit 1
fi

# Half two: NOT tracked, or book text enters the public repository.
if [[ -n "$(git ls-files agent/.si_corpus)" ]]; then
  echo "ABORT: agent/.si_corpus has TRACKED files. Book text must never be" >&2
  echo "       committed to this public repository. Unstage them before deploying." >&2
  git ls-files agent/.si_corpus >&2
  exit 1
fi

if grep -qi 'si_corpus' .dockerignore 2>/dev/null; then
  echo "ABORT: agent/.si_corpus is listed in .dockerignore, so the image would" >&2
  echo "       build without a corpus and Standing Interview could never answer." >&2
  exit 1
fi

CHUNKS=$(python -c "import json;print(json.load(open('$CORPUS',encoding='utf-8'))['chunk_count'])")
echo "==> Corpus OK: ${CHUNKS} chunks, untracked, NOT gitignored, not dockerignored"

# The real gate, against the real corpus and a real model, BEFORE upload.
# Sprint 11: the generic-Kafka defect was invisible to every hermetic test and
# visible in exactly this replay, so a green unit suite is not sufficient here.
#
# SKIP_MODEL_GATE exists for exactly one situation, added 2026-09-30: the
# Anthropic credit balance is exhausted, so the gate CANNOT run at all -- and
# the changes waiting to ship are the fix for the 500s that exhaustion causes,
# plus CSS and a spend cap, none of which can make a model answer worse. The
# gate protects ANSWER QUALITY; skipping it is only defensible when nothing in
# the deploy can affect answer quality, and the Owner has said so.
#
# It is loud, it is recorded in the deploy marker, and it is never the default.
# If you are reaching for it because the gate is failing, that is the gate
# working -- fix the answer, not the script.
if [[ "${SKIP_MODEL_GATE:-}" == "1" ]]; then
  echo
  echo "############################################################"
  echo "## ACCEPTANCE GATE SKIPPED -- SKIP_MODEL_GATE=1"
  echo "## Answer quality is NOT verified by this deploy."
  echo "## Only legitimate when the gate cannot run (no API credit)"
  echo "## AND nothing shipping can change a model answer."
  echo "############################################################"
  echo
  MARKER_SUFFIX="-nogate"
else
  echo "==> Acceptance replay against the local corpus (real model calls)"
  python agent/si_acceptance.py
  MARKER_SUFFIX=""
fi

# Deploy identity marker. REAL INCIDENT (2026-09-29, Sprint 13): the poll
# below used to stop at the first '"loaded":true', which the NEW container
# answered on the first attempt -- and the remote gate then ran while
# Railway was still routing most requests to the OLD container. 7 of 15
# failures, every one of them old-code behaviour, and a wrong conclusion
# was one grep away. The marker is unique per upload, lives in the same
# untracked-but-uploaded directory as the corpus, and is reported by the
# status endpoint; the gate does not run until the remote marker matches
# on three consecutive polls and the old container has had time to drain.
MARKER="deploy-$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD)${MARKER_SUFFIX}"
echo "$MARKER" > agent/.si_corpus/deploy_marker.txt
echo "==> Deploy marker: $MARKER"

echo "==> Deploying the platform backend"
railway up --service agentic-platform-backend

echo "==> Waiting for the NEW container to answer (marker must match 3 polls in a row)"
matches=0
for attempt in $(seq 1 60); do
  remote=$(curl -fsS --max-time 20 "$HOST/api/standing-interview/status" 2>/dev/null \
           | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('deploy_marker') or '')" 2>/dev/null || true)
  if [[ "$remote" == "$MARKER" ]]; then
    matches=$((matches + 1))
    echo "    attempt ${attempt}: new container (${matches}/3)"
    if (( matches >= 3 )); then break; fi
  else
    matches=0
    echo "    attempt ${attempt}: not yet (remote marker: ${remote:-none})"
  fi
  sleep 15
done
if (( matches < 3 )); then
  echo "ABORT: the new container never answered with marker $MARKER. Not gating against an unknown build." >&2
  exit 1
fi
echo "==> Letting the previous container drain (45s) before the gate"
sleep 45

curl -fsS "$HOST/api/standing-interview/status"; echo

# The implementer does not get the last word on its own production success:
# the same assertions that had to pass locally must now pass over HTTP against
# the deployed host, or this exits non-zero and the page is NOT live.
if [[ "${SKIP_MODEL_GATE:-}" == "1" ]]; then
  echo "==> Post-deploy acceptance replay SKIPPED (SKIP_MODEL_GATE=1)."
  echo "    Answer quality on this deploy is UNVERIFIED. Run"
  echo "    'python agent/si_acceptance.py --base-url $HOST' once credit is restored."
else
  echo "==> Acceptance replay against the DEPLOYED host"
  python agent/si_acceptance.py --base-url "$HOST"
fi

echo
echo "==> Standing Interview is live and answering: $HOST/standing-interview"
