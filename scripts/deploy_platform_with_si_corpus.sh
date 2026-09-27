#!/usr/bin/env bash
# Deploy the platform backend WITH the Standing Interview corpus.
#
# WHY THIS SCRIPT EXISTS
# The corpus is built from the private knowledge base and must never enter this
# public repository, but the deployed container needs it or Standing Interview
# cannot answer. `railway up` uploads the local WORKING DIRECTORY rather than a
# git clone (see deploy_customer_app.sh's header, which documents that it does
# not even include .git) -- so a gitignored directory present locally IS
# delivered to the container. That is the whole mechanism.
#
# The ordering matters and is the reason this is a script rather than two
# commands in a runbook: build the corpus FIRST, verify it is non-empty and
# still gitignored, and only then deploy. Deploying without the corpus produces
# a page that loads and cannot answer, which is worse than no page -- and the
# nav entry self-hides in exactly that case, so the failure would be quiet.
#
# Run:  ./scripts/deploy_platform_with_si_corpus.sh
set -euo pipefail

cd "$(dirname "$0")/.."
CORPUS="agent/.si_corpus/corpus.json"

echo "==> Building the Standing Interview corpus from the private knowledge base"
python scripts/build_si_corpus.py

# Fail closed on all three invariants rather than discovering them in production.
if [[ ! -s "$CORPUS" ]]; then
  echo "ABORT: $CORPUS is missing or empty. Refusing to deploy a page that cannot answer." >&2
  exit 1
fi

if ! git check-ignore -q "$CORPUS"; then
  echo "ABORT: $CORPUS is NOT gitignored. Book text must never be committable" >&2
  echo "       to this public repository. Fix .gitignore before deploying." >&2
  exit 1
fi

if grep -qi 'si_corpus' .dockerignore 2>/dev/null; then
  echo "ABORT: agent/.si_corpus is listed in .dockerignore, so the image would" >&2
  echo "       build without a corpus and Standing Interview could never answer." >&2
  exit 1
fi

CHUNKS=$(python -c "import json;print(json.load(open('$CORPUS',encoding='utf-8'))['chunk_count'])")
echo "==> Corpus OK: ${CHUNKS} chunks, gitignored, not dockerignored"

echo "==> Deploying the platform backend"
railway up --service agentic-platform-backend

cat <<'NOTE'

==> Deployed. Verify BEFORE telling anyone the page is live:

      curl -s https://agentic-platform-backend-production.up.railway.app/api/standing-interview/status

    It must report "loaded": true with a non-zero chunk count. If it reports
    false, the corpus did not ship: the page will say so honestly and the nav
    entry will stay hidden, which is the intended failure mode -- but Standing
    Interview is then NOT live, and must not be described as live.
NOTE
