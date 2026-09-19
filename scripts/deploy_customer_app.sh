#!/usr/bin/env bash
# Deploys the Customer App to Railway with a reliable, real commit stamp.
#
# Why this script exists (2026-09-19): `railway up` uploads the local
# working directory, not a fresh GitHub clone -- it does NOT include the
# .git folder, so app/pom.xml's git-commit-id-maven-plugin has no real
# commit info to report (confirmed via Railway's own build log:
# "dotGitDirectory is null, aborting execution!"). The footer's version
# stamp (see app/src/main/resources/static/index.html's loadBuildInfo)
# instead reads DEPLOY_COMMIT_SHA/DEPLOY_COMMIT_TIME from
# GET /actuator/info -- this script is what actually sets those, sourced
# from the real local git HEAD at the moment of deploy, every time. Do
# not deploy the Customer App via a bare `railway up` if the version
# footer matters for that deploy -- use this script instead.
set -euo pipefail

cd "$(dirname "$0")/../app"

COMMIT_SHA="$(git rev-parse --short HEAD)"
COMMIT_TIME="$(git show -s --format=%cI HEAD)"
DIRTY=""
if [ -n "$(git status --porcelain)" ]; then
  DIRTY=" (uncommitted local changes present at deploy time)"
fi

echo "Deploying Customer App -- commit ${COMMIT_SHA}${DIRTY}, committed ${COMMIT_TIME}"

railway variables --service agentic-delivery-customer-app \
  --set "DEPLOY_COMMIT_SHA=${COMMIT_SHA}${DIRTY}" \
  --set "DEPLOY_COMMIT_TIME=${COMMIT_TIME}"

railway up --service agentic-delivery-customer-app
