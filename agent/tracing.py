"""OpenTelemetry tracing for the Python agent platform (local/dev tracing).

Spans: gateway model calls, retrieval, human approval gate. Related spans
share a trace when nested and carry a `run_id` attribute when one is bound
(bind_run_id / run_context).

Exporters (all optional, none needed in CI):
  - always: a bounded in-memory exporter, readable via spans_for_run()
  - OTEL_TRACES_CONSOLE=1 : print spans to stdout
  - OTEL_EXPORTER_OTLP_ENDPOINT set : OTLP/HTTP export to that collector
  - OTEL_SDK_DISABLED=true : tracing is a pure no-op (no spans, no export)
No attribute here may carry raw queries, document text, API keys or owner
tokens: queries are length + short hash only.
"""
import contextlib
import contextvars
import hashlib
import os
import threading

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

_run_id_var: contextvars.ContextVar = contextvars.ContextVar("asd_run_id", default=None)
_lock = threading.Lock()
_provider = None
_memory = None
MAX_BUFFERED_SPANS = 5000


def disabled() -> bool:
    return os.environ.get("OTEL_SDK_DISABLED", "").strip().lower() == "true"


def _setup():
    global _provider, _memory
    with _lock:
        if _provider is not None:
            return
        _memory = InMemorySpanExporter()
        _provider = TracerProvider(resource=Resource.create({"service.name": "asd-agent-platform"}))
        _provider.add_span_processor(SimpleSpanProcessor(_memory))
        if os.environ.get("OTEL_TRACES_CONSOLE", "").strip() in ("1", "true"):
            _provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"):
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            _provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))


def reset_for_tests() -> None:
    """Drop the provider so env changes (console/OTLP/disabled) re-apply."""
    global _provider, _memory
    with _lock:
        _provider = None
        _memory = None


def bind_run_id(run_id):
    """Bind run_id for this context; returns a token for contextvars reset."""
    return _run_id_var.set(run_id)


def current_run_id():
    return _run_id_var.get()


def query_fingerprint(query: str) -> dict:
    q = query or ""
    return {"query.length": len(q), "query.sha256_12": hashlib.sha256(q.encode("utf-8")).hexdigest()[:12]}


class _NoopSpan:
    def set_attribute(self, *a, **k): pass
    def set_attributes(self, *a, **k): pass
    def record_exception(self, *a, **k): pass


@contextlib.contextmanager
def span(name: str, **attributes):
    """Start a span; yields an object with set_attribute(). No-op if disabled."""
    if disabled():
        yield _NoopSpan()
        return
    _setup()
    attrs = {k: v for k, v in attributes.items() if v is not None}
    rid = _run_id_var.get()
    if rid is not None:
        attrs["run_id"] = rid
    with _provider.get_tracer("asd.agent").start_as_current_span(name, attributes=attrs) as s:
        yield s


def finished_spans() -> list:
    if _memory is None:
        return []
    spans = list(_memory.get_finished_spans())
    if len(spans) > MAX_BUFFERED_SPANS:
        _memory.clear()
        spans = spans[-MAX_BUFFERED_SPANS // 2:]
    return spans


def spans_for_run(run_id: str) -> list[dict]:
    out = []
    for s in finished_spans():
        if (s.attributes or {}).get("run_id") == run_id:
            out.append({
                "name": s.name,
                "trace_id": format(s.context.trace_id, "032x"),
                "span_id": format(s.context.span_id, "016x"),
                "parent_span_id": format(s.parent.span_id, "016x") if s.parent else None,
                "duration_ms": round((s.end_time - s.start_time) / 1e6, 2),
                "status": s.status.status_code.name,
                "attributes": dict(s.attributes),
            })
    return out
