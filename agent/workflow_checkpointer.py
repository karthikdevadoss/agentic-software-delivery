"""
Postgres checkpoint store for the durable workflow -- Sprint 13, BL-093.

A LangGraph BaseCheckpointSaver backed by two tables in the SAME Postgres
that already holds the event ledger (Owner decision 2026-09-29: no new
infrastructure, no new credential). The DDL lives in
infra/event-ledger/schema.sql and is applied by event_ledger.ensure_schema(),
exactly like the ledger's own table.

The semantics are a direct port of langgraph.checkpoint.memory.MemorySaver
(read from the installed langgraph-checkpoint 4.2.0, not from memory):
  * one row per (thread_id, checkpoint_ns, checkpoint_id) holding the whole
    checkpoint -- channel_values included -- serialised with the library's
    own typed serializer, plus metadata and the parent checkpoint id;
  * one row per pending write (thread, ns, checkpoint, task, idx) so an
    interrupt() and its Command(resume=...) survive a process death;
  * get_tuple() returns the latest checkpoint for a thread, or a specific
    one when checkpoint_id is given, with its pending writes.

Storing the whole checkpoint per row (rather than MemorySaver's per-channel
blob de-duplication) is a deliberate simplification: checkpoints here are a
few kilobytes, and one readable row per step is what an operator debugging a
stuck workflow actually wants.

Fail-closed: a row whose blob cannot be deserialised raises, and the caller
(durable_workflow.describe_workflow) reports the workflow as CORRUPT rather
than continuing from a partial state.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
    get_checkpoint_metadata,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

import event_ledger


def _cfg(thread_id: str, ns: str, checkpoint_id: str | None) -> dict:
    return {"configurable": {"thread_id": thread_id, "checkpoint_ns": ns,
                             "checkpoint_id": checkpoint_id}}


class PostgresWorkflowCheckpointer(BaseCheckpointSaver[str]):
    """Sync-only, which is all the workflow uses. `connect` is injectable so
    the hermetic tests run against a fake connection factory."""

    def __init__(self, connect=None):
        super().__init__(serde=JsonPlusSerializer())
        self._connect = connect or event_ledger._connect   # noqa: SLF001 - same DB, same guards
        self._schema_ready = False

    # --- plumbing ------------------------------------------------------------
    def _conn(self):
        if not self._schema_ready:
            event_ledger.ensure_schema()      # creates workflow_* tables too
            self._schema_ready = True
        return self._connect()

    def _load_tuple(self, thread_id: str, ns: str, row, cur) -> CheckpointTuple:
        checkpoint_id, ckpt_type, ckpt_blob, meta_type, meta_blob, parent_id = row
        checkpoint: Checkpoint = self.serde.loads_typed((ckpt_type, bytes(ckpt_blob)))
        metadata: CheckpointMetadata = self.serde.loads_typed((meta_type, bytes(meta_blob)))
        # Fail closed. msgpack decodes almost any byte string to SOMETHING (a
        # NUL byte followed by garbage decodes to the integer 0), so "it
        # deserialised" proves nothing. A checkpoint is a dict carrying
        # channel_values, or the row is corrupt and the caller must not resume.
        if not isinstance(checkpoint, dict) or "channel_values" not in checkpoint \
                or not isinstance(metadata, dict):
            raise ValueError(f"corrupt checkpoint row {thread_id}/{checkpoint_id}: "
                             f"decoded to {type(checkpoint).__name__}, not a checkpoint")
        cur.execute(
            "SELECT task_id, channel, blob_type, blob, idx FROM workflow_checkpoint_writes "
            "WHERE thread_id=%s AND checkpoint_ns=%s AND checkpoint_id=%s ORDER BY task_id, idx",
            (thread_id, ns, checkpoint_id))
        writes = [(task_id, channel, self.serde.loads_typed((bt, bytes(b))))
                  for task_id, channel, bt, b, _idx in cur.fetchall()]
        return CheckpointTuple(
            config=_cfg(thread_id, ns, checkpoint_id),
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=_cfg(thread_id, ns, parent_id) if parent_id else None,
            pending_writes=writes,
        )

    # --- BaseCheckpointSaver -------------------------------------------------
    def get_tuple(self, config: dict) -> CheckpointTuple | None:
        thread_id = config["configurable"]["thread_id"]
        ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = get_checkpoint_id(config)
        conn = self._conn()
        try:
            with conn, conn.cursor() as cur:
                if checkpoint_id:
                    cur.execute(
                        "SELECT checkpoint_id, checkpoint_type, checkpoint, metadata_type, metadata, parent_checkpoint_id "
                        "FROM workflow_checkpoints WHERE thread_id=%s AND checkpoint_ns=%s AND checkpoint_id=%s",
                        (thread_id, ns, checkpoint_id))
                else:
                    cur.execute(
                        "SELECT checkpoint_id, checkpoint_type, checkpoint, metadata_type, metadata, parent_checkpoint_id "
                        "FROM workflow_checkpoints WHERE thread_id=%s AND checkpoint_ns=%s "
                        "ORDER BY checkpoint_id DESC LIMIT 1",
                        (thread_id, ns))
                row = cur.fetchone()
                if row is None:
                    return None
                return self._load_tuple(thread_id, ns, row, cur)
        finally:
            conn.close()

    def list(self, config: dict | None, *, filter: dict[str, Any] | None = None,
             before: dict | None = None, limit: int | None = None) -> Iterator[CheckpointTuple]:
        where, params = [], []
        if config:
            where.append("thread_id=%s"); params.append(config["configurable"]["thread_id"])
            ns = config["configurable"].get("checkpoint_ns")
            if ns is not None:
                where.append("checkpoint_ns=%s"); params.append(ns)
            cid = get_checkpoint_id(config)
            if cid:
                where.append("checkpoint_id=%s"); params.append(cid)
        if before and get_checkpoint_id(before):
            where.append("checkpoint_id < %s"); params.append(get_checkpoint_id(before))
        sql = ("SELECT thread_id, checkpoint_ns, checkpoint_id, checkpoint_type, checkpoint, "
               "metadata_type, metadata, parent_checkpoint_id FROM workflow_checkpoints")
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY checkpoint_id DESC"
        conn = self._conn()
        try:
            with conn, conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                n = 0
                for thread_id, ns, *rest in rows:
                    tup = self._load_tuple(thread_id, ns, tuple(rest), cur)
                    if filter and not all(tup.metadata.get(k) == v for k, v in filter.items()):
                        continue
                    if limit is not None and n >= limit:
                        break
                    n += 1
                    yield tup
        finally:
            conn.close()

    def put(self, config: dict, checkpoint: Checkpoint, metadata: CheckpointMetadata,
            new_versions: ChannelVersions) -> dict:
        thread_id = config["configurable"]["thread_id"]
        ns = config["configurable"].get("checkpoint_ns", "")
        parent_id = config["configurable"].get("checkpoint_id")
        ckpt_type, ckpt_blob = self.serde.dumps_typed(checkpoint)
        meta_type, meta_blob = self.serde.dumps_typed(get_checkpoint_metadata(config, metadata))
        conn = self._conn()
        try:
            with conn, conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO workflow_checkpoints (thread_id, checkpoint_ns, checkpoint_id, "
                    "parent_checkpoint_id, checkpoint_type, checkpoint, metadata_type, metadata) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id) DO UPDATE SET "
                    "checkpoint_type=EXCLUDED.checkpoint_type, checkpoint=EXCLUDED.checkpoint, "
                    "metadata_type=EXCLUDED.metadata_type, metadata=EXCLUDED.metadata",
                    (thread_id, ns, checkpoint["id"], parent_id, ckpt_type,
                     psycopg2_binary(ckpt_blob), meta_type, psycopg2_binary(meta_blob)))
        finally:
            conn.close()
        return _cfg(thread_id, ns, checkpoint["id"])

    def put_writes(self, config: dict, writes: Sequence[tuple[str, Any]], task_id: str,
                   task_path: str = "") -> None:
        thread_id = config["configurable"]["thread_id"]
        ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]
        conn = self._conn()
        try:
            with conn, conn.cursor() as cur:
                for idx, (channel, value) in enumerate(writes):
                    widx = WRITES_IDX_MAP.get(channel, idx)
                    bt, blob = self.serde.dumps_typed(value)
                    # MemorySaver: a non-special write that already exists is kept
                    # (first writer wins); special writes (idx < 0) are replaced.
                    cur.execute(
                        "INSERT INTO workflow_checkpoint_writes (thread_id, checkpoint_ns, checkpoint_id, "
                        "task_id, idx, channel, blob_type, blob, task_path) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                        "ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id, task_id, idx) DO "
                        + ("UPDATE SET channel=EXCLUDED.channel, blob_type=EXCLUDED.blob_type, "
                           "blob=EXCLUDED.blob, task_path=EXCLUDED.task_path" if widx < 0 else "NOTHING"),
                        (thread_id, ns, checkpoint_id, task_id, widx, channel, bt,
                         psycopg2_binary(blob), task_path))
        finally:
            conn.close()

    def delete_thread(self, thread_id: str) -> None:
        conn = self._conn()
        try:
            with conn, conn.cursor() as cur:
                cur.execute("DELETE FROM workflow_checkpoint_writes WHERE thread_id=%s", (thread_id,))
                cur.execute("DELETE FROM workflow_checkpoints WHERE thread_id=%s", (thread_id,))
        finally:
            conn.close()

    def get_next_version(self, current: str | None, channel: None) -> str:
        # Same monotonic scheme as MemorySaver: "<int>.<random>" so that a
        # string comparison orders versions correctly.
        import random
        if current is None:
            current_v = 0
        elif isinstance(current, int):
            current_v = current
        else:
            current_v = int(current.split(".")[0])
        return f"{current_v + 1:032}.{random.random():016}"


def psycopg2_binary(blob: bytes):
    import psycopg2
    return psycopg2.Binary(blob)


DDL = """
-- Sprint 13 (BL-093): durable workflow checkpoints, applied by
-- event_ledger.ensure_schema() alongside delivery_events. One row per
-- LangGraph checkpoint (whole checkpoint, typed-serialised) and one row per
-- pending write, so an approval interrupt and its resume survive a restart.
CREATE TABLE IF NOT EXISTS workflow_checkpoints (
    thread_id              TEXT NOT NULL,
    checkpoint_ns          TEXT NOT NULL DEFAULT '',
    checkpoint_id          TEXT NOT NULL,
    parent_checkpoint_id   TEXT,
    checkpoint_type        TEXT NOT NULL,
    checkpoint             BYTEA NOT NULL,
    metadata_type          TEXT NOT NULL,
    metadata               BYTEA NOT NULL,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);
CREATE TABLE IF NOT EXISTS workflow_checkpoint_writes (
    thread_id              TEXT NOT NULL,
    checkpoint_ns          TEXT NOT NULL DEFAULT '',
    checkpoint_id          TEXT NOT NULL,
    task_id                TEXT NOT NULL,
    idx                    INTEGER NOT NULL,
    channel                TEXT NOT NULL,
    blob_type              TEXT NOT NULL,
    blob                   BYTEA NOT NULL,
    task_path              TEXT NOT NULL DEFAULT '',
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);
CREATE INDEX IF NOT EXISTS workflow_checkpoints_thread_latest
    ON workflow_checkpoints (thread_id, checkpoint_ns, checkpoint_id DESC);
"""
