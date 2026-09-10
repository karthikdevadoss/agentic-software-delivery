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

FROM python:3.12-slim-bookworm

# git: real local commits (_run_controlled(["git", ...])).
# openjdk-17-jdk-headless: app/mvnw needs a JDK on PATH (Maven itself is
#   downloaded by the wrapper on first run).
# curl + ca-certificates: fetch the Railway CLI release below.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git openjdk-17-jdk-headless curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

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

# git_commit provenance (agent/web_server.py's Run.git_commit_before) and
# the trainer's real `git commit` step both need a usable repo identity —
# this image runs as a fresh checkout with no prior local commits, so
# make sure git itself is at least configured; the actual clone/history
# is whatever was COPYed in at build time.
RUN git config --global --add safe.directory /repo \
    && git config --global user.email "agent@agentic-software-delivery.local" \
    && git config --global user.name "Agentic Software Delivery (platform)"

WORKDIR /repo/agent

# PORT is provided by Railway at runtime; web_server.py reads it (falls
# back to 8420 for local `docker run` testing without PORT set).
CMD ["python", "web_server.py"]
