#!/usr/bin/env bash
# Run a Claude Code session with OpenTelemetry metrics on, exported to the
# console. Zero infrastructure: no collector, no backend, no daemon, nothing
# to install or keep running.
#
# WHY THIS EXISTS
# Claude Code's SessionEnd hook (agent/claude_code_hook.py) captures real usage
# only AFTER a session ends. That leaves a live blind spot during the session
# itself -- the exact window in which this project's documented cost incident
# happened (a real pay-as-you-go credit exhausted in under 7 minutes, while
# nothing in-session surfaced the burn rate). Claude Code already emits real
# OTel metrics, including claude_code.cost.usage in USD; they were simply never
# switched on. This turns them on for one session at a time.
#
# DELIBERATELY MINIMAL (2026-09-25 decision)
#   - console exporter only: no OTLP endpoint, no collector, no storage
#   - opt-in per session: NOT enabled globally, so normal sessions stay quiet
#   - does not touch the event ledger, the SessionEnd hook, or any config
#   - nothing here is a spend LIMIT. It is visibility only. Stopping on a
#     threshold is a separate, later decision (see the Architecture V1 dossier's
#     OPEN-02) and is deliberately not implemented here.
#
# HOW TO DEEPEN IT LATER (no rework of this file required)
#   Swap the exporter without changing anything else:
#     OTEL_METRICS_EXPORTER=otlp
#     OTEL_EXPORTER_OTLP_PROTOCOL=grpc
#     OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
#   ...pointed at a local collector, Grafana/Tempo, or a receiver that writes
#   into the existing Postgres event ledger. The variable names below are the
#   standard OTel ones, so none of this is Claude-Code-specific lock-in.
#
# USAGE
#   scripts/otel_session.sh            # launch claude with telemetry on
#   scripts/otel_session.sh --print    # just print the exports, launch nothing
#
# REAL METRICS EMITTED (per Claude Code's own monitoring docs, verified 2026-09-25)
#   claude_code.cost.usage             USD    cost of the session
#   claude_code.token.usage            tokens tokens used
#   claude_code.session.count                 sessions started
#   claude_code.active_time.total      s      active time
#   claude_code.lines_of_code.count           lines modified
#   claude_code.commit.count                  git commits created
#   claude_code.pull_request.count            PRs created
#   claude_code.code_edit_tool.decision       edit-permission decisions
# Attributes include model and (for subagent work) the agent name, so per-model
# and per-subagent spend is separable at the point of export.

set -euo pipefail

# 10s instead of the 60s default: a burn-rate problem needs to be visible while
# it is still happening, not a minute later. Costs nothing -- console export.
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=console
export OTEL_METRIC_EXPORT_INTERVAL=10000

if [[ "${1:-}" == "--print" ]]; then
  echo "export CLAUDE_CODE_ENABLE_TELEMETRY=1"
  echo "export OTEL_METRICS_EXPORTER=console"
  echo "export OTEL_METRIC_EXPORT_INTERVAL=10000"
  echo
  echo "# PowerShell equivalent:"
  echo '#   $env:CLAUDE_CODE_ENABLE_TELEMETRY=1'
  echo '#   $env:OTEL_METRICS_EXPORTER="console"'
  echo '#   $env:OTEL_METRIC_EXPORT_INTERVAL=10000'
  exit 0
fi

echo "OpenTelemetry ON for this session (console exporter, ${OTEL_METRIC_EXPORT_INTERVAL}ms interval)."
echo "Visibility only -- this does NOT cap or stop spend."
echo
exec claude "$@"
