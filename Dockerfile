# Agentic Software Delivery — platform backend (agent/web_server.py).
#
# Deliberately NOT the Customer app's own deployment (that stays Nixpacks/
# Maven-auto-detected, root dir app/, its own Railway project — see
# docs/RESOURCE_REGISTRY.md). This image is for the ORCHESTRATION server
# itself: Workbench/Dashboard/Usage/Learn/Profile, plus everything the
# Workbench's bounded-autonomy path needs to actually operate — real git
# commits, a real Maven build/test of app/, and (once RAILWAY_TOKEN is
# configured) a real `railway up` deploy of the Customer app. Built from
# the repo root, not a subdirectory, because the container needs both
# agent/ and app/ on disk together.
#
# Runtime tool dependencies verified directly from agent/web_server.py and
# agent/build_tools.py's actual subprocess calls (see docs/DECISIONS.md),
# not assumed: git, a JDK (for app/mvnw), and the Railway CLI.

# JDK 21 source stage: Debian bookworm's own apt repos only carry JDK 17
# (openjdk-21-jdk-headless: "Unable to locate package" -- confirmed via a
# real failed Railway build, not assumed), so JDK 21 is copied from
# Eclipse Temurin's official image instead of installed via apt.
FROM eclipse-temurin:21-jdk-jammy AS jdk

FROM python:3.12-slim-bookworm

# git: real local commits (_run_controlled(["git", ...])).
# JDK 21 (copied from the eclipse-temurin stage above): app/mvnw needs a
#   JDK on PATH (Maven itself is downloaded by the wrapper on first run).
#   REAL PRODUCTION BUG found via live browser testing of the Incident
#   Triage Lab (2026-09-15): this image previously installed
#   openjdk-17-jdk-headless via apt, but app/pom.xml's <java.version> was
#   bumped to 21 in an earlier session (MASTER BUILD PHASE) -- every real
#   mvnw compile/test invocation running INSIDE this container
#   (Workbench's agent/build_tools.py, the Triage Lab's verify step) was
#   silently broken ("release version 21 not supported"), invisible until
#   something actually exercised a real compile/test from within this
#   specific container rather than a local dev machine that happened to
#   have a newer JDK already installed. openjdk-21-jdk-headless is not a
#   real apt package in Debian bookworm (confirmed via a real failed
#   build, not assumed), hence copying a real JDK from Temurin's image
#   instead of a second, different apt attempt.
# curl + ca-certificates: fetch the Railway CLI release below.
COPY --from=jdk /opt/java/openjdk /opt/java/openjdk
ENV JAVA_HOME=/opt/java/openjdk
ENV PATH="${JAVA_HOME}/bin:${PATH}"
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && java -version

# Railway CLI — exact version/URL pattern confirmed from the real,
# installed @railway/cli npm package's own postinstall config (not
# guessed): statically-linked musl binary, no Node/npm needed at runtime.
RUN curl -fsSL "https://github.com/railwayapp/cli/releases/download/v5.50.2/railway-v5.50.2-x86_64-unknown-linux-musl.tar.gz" \
      -o /tmp/railway.tar.gz \
    && tar -xzf /tmp/railway.tar.gz -C /usr/local/bin railway \
    && chmod +x /usr/local/bin/railway \
    && rm /tmp/railway.tar.gz

WORKDIR /repo

# Java/Maven layer cached separately from the Python layer below.
# chmod +x is REQUIRED, not defensive: this repo is built from a Windows
# host, and Docker's COPY does not preserve/infer a POSIX executable bit
# from a Windows filesystem — without this, ./mvnw fails at runtime with
# "Permission denied" (found via a real failed acceptance run against
# this exact image, not assumed — see docs/DECISIONS.md).
COPY app/mvnw app/mvnw.cmd app/pom.xml ./app/
COPY app/.mvn ./app/.mvn
RUN chmod +x app/mvnw && cd app && ./mvnw -q -B dependency:go-offline

COPY agent/requirements.txt ./agent/requirements.txt
RUN pip install --no-cache-dir -r agent/requirements.txt

COPY . .
RUN chmod +x app/mvnw

# agent/.backend_rag_index/ is gitignored (derived/build data, same
# convention as the sibling whole-repo RAG index) -- nothing previously
# built it automatically, because until the "Ask the Codebase" public
# route (2026-09-17), this index was only ever built manually by a
# developer running agent/backend_acceptance.py, never at live-request
# time. Built into the IMAGE here (not lazily at request time or
# container startup) so the very first real visitor to /ask-codebase
# after a fresh deploy gets a real, already-built index -- not a slow
# multi-minute cold build blocking their request, and not a startup delay
# risking Railway's health check.
RUN cd agent && python backend_rag_index.py

# git_commit provenance (agent/web_server.py's Run.git_commit_before) and
# the trainer's real `git commit` step both need a usable repo identity —
# this image runs as a fresh checkout with no prior local commits, so
# make sure git itself is at least configured; the actual clone/history
# is whatever was COPYed in at build time.
RUN git config --global --add safe.directory /repo \
    && git config --global user.email "agent@agentic-software-delivery.local" \
    && git config --global user.name "Agentic Software Delivery (platform)"

# ROOT CAUSE (real production incident, run trainer-6aedf022, 2026-09-10):
# `railway up`'s upload of the local working directory does not include
# .git (confirmed: the deployed container had no .git anywhere under
# /repo at all — not a permissions/ownership issue, which would raise a
# different git error). COPY . . therefore never had a .git to copy, so
# every real trainer commit attempt failed with "fatal: not a git
# repository" at the COMMITTING stage, after real API cost had already
# been spent on investigation/proposal/build. Fix: give the image its
# own real, usable git repository at build time if none was uploaded —
# this workspace never pushes to/pulls from GitHub, it only needs a
# genuine local repo so `git commit`/`git rev-parse HEAD` work for the
# trainer's provenance-commit-then-deploy flow.
RUN if [ ! -d .git ]; then \
      git init -q && git add -A && git commit -q -m "Baseline snapshot (Railway build context has no .git)"; \
    fi

WORKDIR /repo/agent

# PORT is provided by Railway at runtime; web_server.py reads it (falls
# back to 8420 for local `docker run` testing without PORT set).
CMD ["python", "web_server.py"]
