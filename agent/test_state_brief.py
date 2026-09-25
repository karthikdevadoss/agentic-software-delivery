"""
Tests for agent/state_brief.py -- the session-startup brief.

WHAT THESE TESTS ARE ACTUALLY PROTECTING
The brief replaces a full read of docs/PROJECT_STATE.json, docs/PROJECT_STATUS.md
and docs/ACTION_QUEUE.json at session startup. That is a safe trade ONLY while
it is impossible for the brief to quietly omit current or open information. So
the tests here are not "does it render nicely" -- they are:

  * every ACTIVE queue item in the REAL file reaches the REAL rendered output
    (asserted by id, against the real documents, not a fixture);
  * every status value the queue declares is classified somewhere;
  * a renamed heading / an unclassified status / a missing state key makes it
    FAIL, not silently produce a shorter brief;
  * staleness is reported when the recorded commit is behind HEAD, and not
    reported when it is current;
  * it writes nothing to disk.

Each guard is exercised against a deliberately seeded bad input, so the guard
has been observed failing for the intended reason rather than merely passing.

Run: python agent/test_state_brief.py
"""

import io
import json
import pathlib
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import state_brief as sb


REAL_QUEUE = json.loads(sb.ACTION_QUEUE.read_text(encoding="utf-8"))
REAL_STATE = json.loads(sb.PROJECT_STATE.read_text(encoding="utf-8"))


def render_real() -> str:
    return sb.render(sb.build())


class RealDocumentsTestCase(unittest.TestCase):
    """Runs against the real committed documents -- no fixtures. A fixture
    would prove the code works on data the test itself invented; the risk being
    guarded is that the code drifts away from the REAL documents."""

    def test_every_active_queue_item_reaches_the_rendered_brief(self):
        """The core no-silent-loss guarantee."""
        active = [i for i in REAL_QUEUE["items"] if i["status"] in sb.ACTIVE_STATUSES]
        self.assertGreater(len(active), 0, "queue has no active items -- test is not exercising anything")
        out = render_real()
        for item in active:
            self.assertIn(
                item["id"], out,
                f"ACTIVE item {item['id']} ({item['status']}) is absent from the brief. "
                "Startup would never see it.",
            )

    def test_no_terminal_item_is_misreported_as_active(self):
        out = render_real()
        active_line = next(l for l in out.splitlines() if "ACTIVE of" in l)
        real_active = sum(1 for i in REAL_QUEUE["items"] if i["status"] in sb.ACTIVE_STATUSES)
        self.assertIn(f"{real_active} ACTIVE of {len(REAL_QUEUE['items'])} total", active_line)

    def test_every_declared_queue_status_is_classified(self):
        """docs/ACTION_QUEUE.json declares its own vocabulary in _status_values.
        Any declared value that is in neither bucket could hide open work."""
        declared = set(REAL_QUEUE["_status_values"])
        unclassified = declared - (sb.ACTIVE_STATUSES | sb.TERMINAL_STATUSES)
        self.assertEqual(
            set(), unclassified,
            f"status value(s) declared by ACTION_QUEUE.json but classified by neither "
            f"ACTIVE_STATUSES nor TERMINAL_STATUSES: {sorted(unclassified)}",
        )

    def test_required_status_headings_all_exist_in_the_real_file(self):
        sections = sb.collect_status_sections()
        self.assertEqual(list(sections), sb.REQUIRED_STATUS_HEADINGS)
        for heading, body in sections.items():
            self.assertTrue(body.strip(), f"{heading} extracted empty")

    def test_required_state_keys_all_exist_in_the_real_file(self):
        for key in sb.STATE_KEYS:
            self.assertIn(key, REAL_STATE, f"PROJECT_STATE.json has no {key!r}")

    def test_next_action_and_current_ticket_are_carried_verbatim(self):
        out = render_real()
        # First 60 chars is enough to prove it is the real string, not a label.
        self.assertIn(str(REAL_STATE["next_action"])[:60], out)
        self.assertIn(str(REAL_STATE["current_ticket"])[:60], out)

    def test_anything_not_fully_verified_is_named_not_just_counted(self):
        brief = sb.build()
        summary = brief["state"]["_verification_summary"]
        for name, entry in REAL_STATE["verification_state"].items():
            if name.startswith("_"):
                continue
            if entry.get("status") == "not_verified":
                self.assertTrue(
                    any(name in n for n in summary["needs_attention"]),
                    f"{name} is not_verified but is not named in the brief",
                )

    def test_brief_writes_nothing_to_disk(self):
        """A generated file would become a fourth state document that drifts."""
        docs = sb.REPO_ROOT / "docs"
        before = {p.name: p.stat().st_mtime_ns for p in docs.iterdir() if p.is_file()}
        agent_before = {p.name for p in (sb.REPO_ROOT / "agent").iterdir() if p.is_file()}
        with redirect_stdout(io.StringIO()):
            sb.main()
        after = {p.name: p.stat().st_mtime_ns for p in docs.iterdir() if p.is_file()}
        self.assertEqual(before, after, "state_brief modified something under docs/")
        agent_after = {p.name for p in (sb.REPO_ROOT / "agent").iterdir() if p.is_file()}
        self.assertEqual(agent_before, agent_after, "state_brief created a file under agent/")


class SeededFailureTestCase(unittest.TestCase):
    """Each guard is pointed at a deliberately broken copy of the real document
    and observed to FAIL for the intended reason. Without this, a guard that
    never fires is indistinguishable from a guard that cannot fire."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="state_brief_seed_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _copy(self, src: pathlib.Path) -> pathlib.Path:
        dst = self.tmp / src.name
        shutil.copy2(src, dst)
        return dst

    def test_unclassified_queue_status_fails_loudly(self):
        q = json.loads(sb.ACTION_QUEUE.read_text(encoding="utf-8"))
        q["items"][0]["status"] = "awaiting_something_new"
        path = self.tmp / "ACTION_QUEUE.json"
        path.write_text(json.dumps(q), encoding="utf-8")
        with mock.patch.object(sb, "ACTION_QUEUE", path):
            with self.assertRaises(SystemExit) as ctx:
                sb.collect_queue()
        self.assertIn("awaiting_something_new", str(ctx.exception))
        self.assertIn("unclassified status", str(ctx.exception))

    def test_renamed_status_heading_fails_loudly(self):
        text = sb.PROJECT_STATUS.read_text(encoding="utf-8")
        broken = text.replace("# Exact next development step", "# Next step (renamed)")
        self.assertNotEqual(text, broken, "seed did not apply -- heading not found")
        path = self.tmp / "PROJECT_STATUS.md"
        path.write_text(broken, encoding="utf-8")
        with mock.patch.object(sb, "PROJECT_STATUS", path):
            with self.assertRaises(SystemExit) as ctx:
                sb.collect_status_sections()
        self.assertIn("# Exact next development step", str(ctx.exception))

    def test_missing_state_key_fails_loudly(self):
        state = dict(REAL_STATE)
        del state["next_action"]
        with self.assertRaises(SystemExit) as ctx:
            sb.collect_state(state)
        self.assertIn("next_action", str(ctx.exception))

    def test_a_removed_active_item_would_be_detected(self):
        """Proves the no-silent-loss assertion above can actually fail: drop an
        active item from the data the brief reads and confirm its id disappears
        from the output. If this passed with the id still present, the primary
        assertion would be vacuous."""
        q = json.loads(sb.ACTION_QUEUE.read_text(encoding="utf-8"))
        victim = next(i for i in q["items"] if i["status"] in sb.ACTIVE_STATUSES)
        q["items"] = [i for i in q["items"] if i["id"] != victim["id"]]
        path = self.tmp / "ACTION_QUEUE.json"
        path.write_text(json.dumps(q), encoding="utf-8")
        with mock.patch.object(sb, "ACTION_QUEUE", path):
            out = sb.render(sb.build())
        self.assertNotIn(victim["id"], out)


class StalenessTestCase(unittest.TestCase):
    def test_stale_state_produces_a_visible_banner(self):
        """The real file is currently behind HEAD; assert the banner fires for
        a commit that is definitely behind (the repo's first commit)."""
        first = sb._git("rev-list", "--max-parents=0", "HEAD").split()[0][:7]
        state = dict(REAL_STATE, last_verified_code_commit=first)
        stale = sb.collect_staleness(state)
        self.assertIsNotNone(stale["commits_behind"])
        self.assertGreater(stale["commits_behind"], 0)
        brief = sb.build()
        brief["staleness"] = stale
        out = sb.render(brief)
        self.assertIn("STALE STATE", out)
        self.assertIn("HISTORICAL CLAIM", out)

    def test_current_state_produces_no_stale_banner(self):
        head = sb._git("rev-parse", "--short", "HEAD")
        state = dict(REAL_STATE, last_verified_code_commit=head)
        stale = sb.collect_staleness(state)
        self.assertEqual(0, stale["commits_behind"])
        brief = sb.build()
        brief["staleness"] = stale
        out = sb.render(brief)
        self.assertNotIn("STALE STATE", out)
        self.assertIn("State is current with HEAD", out)

    def test_unresolvable_commit_is_reported_as_unknown_not_as_current(self):
        """Fail-visible, not fail-silent: an unknown sha must never render as
        'current'."""
        state = dict(REAL_STATE, last_verified_code_commit="0000000")
        stale = sb.collect_staleness(state)
        self.assertIsNone(stale["commits_behind"])
        brief = sb.build()
        brief["staleness"] = stale
        out = sb.render(brief)
        self.assertIn("STALENESS UNKNOWN", out)
        self.assertNotIn("State is current with HEAD", out)


class SizeTestCase(unittest.TestCase):
    def test_brief_is_far_smaller_than_the_three_source_documents(self):
        """The whole point. If this ever fails, the brief has stopped being a
        summary and the reduction claim in CLAUDE.md is no longer true."""
        sources = sum(
            p.stat().st_size for p in (sb.PROJECT_STATE, sb.PROJECT_STATUS, sb.ACTION_QUEUE)
        )
        rendered = len(render_real().encode("utf-8"))
        self.assertLess(rendered, sources * 0.10, f"brief is {rendered} B of {sources} B sources")


if __name__ == "__main__":
    unittest.main()
