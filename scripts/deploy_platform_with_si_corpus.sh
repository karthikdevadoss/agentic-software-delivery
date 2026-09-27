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
echo "==> Acceptance replay against the local corpus (real model calls)"
python agent/si_acceptance.py

echo "==> Deploying the platform backend"
railway up --service agentic-platform-backend

echo "==> Waiting for the new deploy to report a loaded corpus"
for attempt in $(seq 1 40); do
  if curl -fsS --max-time 20 "$HOST/api/standing-interview/status" 2>/dev/null \
      | grep -q '"loaded":true'; then
    echo "    corpus loaded on attempt ${attempt}"
    break
  fi
  sleep 15
done

curl -fsS "$HOST/api/standing-interview/status"; echo

# The implementer does not get the last word on its own production success:
# the same assertions that had to pass locally must now pass over HTTP against
# the deployed host, or this exits non-zero and the page is NOT live.
echo "==> Acceptance replay against the DEPLOYED host"
python agent/si_acceptance.py --base-url "$HOST"

echo
echo "==> Standing Interview is live and answering: $HOST/standing-interview"
