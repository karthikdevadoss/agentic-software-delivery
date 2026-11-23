"""Unmanaged, read-only mapping of the EXISTING delivery_events table
(infra/event-ledger/schema.sql). Django never creates/alters it. Only the
columns this slice displays are mapped; `payload` (JSONB) is deliberately not
mapped, so raw event payloads are not surfaced in the admin."""
from django.db import models


class ReadOnlyError(Exception):
    pass


class LedgerEvent(models.Model):
    event_id = models.TextField(primary_key=True)
    timestamp_utc = models.DateTimeField()
    event_type = models.TextField()
    stage = models.TextField(null=True)
    status = models.TextField(null=True)
    session_id = models.TextField(null=True)
    run_id = models.TextField(null=True)
    requirement_id = models.TextField(null=True)
    source = models.TextField(null=True)
    activity_class = models.TextField(null=True)
    duration_ms = models.FloatField(null=True)
    provider = models.TextField(null=True)
    model = models.TextField(null=True)
    input_tokens = models.IntegerField(null=True)
    output_tokens = models.IntegerField(null=True)
    cache_read_tokens = models.IntegerField(null=True)
    cache_write_tokens = models.IntegerField(null=True)
    cost_usd = models.FloatField(null=True)
    pricing_version = models.TextField(null=True)
    evidence_quality = models.TextField(null=True)
    backfill_source = models.TextField(null=True)

    class Meta:
        managed = False
        db_table = "delivery_events"
        ordering = ["-timestamp_utc"]
        verbose_name = "ledger event"

    def save(self, *args, **kwargs):
        raise ReadOnlyError("the ledger is append-only and read-only from this app")

    def delete(self, *args, **kwargs):
        raise ReadOnlyError("the ledger is append-only and read-only from this app")

    def __str__(self):
        return f"{self.event_type} {self.event_id}"
