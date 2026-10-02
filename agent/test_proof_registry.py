"""Tests for the public proof surface gate.

Structure, deliberately:

  1. the real registry passes, and its shape is what the release contract says;
  2. every check is then shown REJECTING a seeded mutation.

Part 2 is the part that makes part 1 mean anything. A detector that has only
ever been run against clean input has not been shown to detect -- this project
learned that the expensive way in Sprint 4 (BL-032), where a careful root-cause
read reached a wrong conclusion because the evidence field it trusted had been
truncated upstream and nobody had checked the reader against a known-bad case.

Every mutation below is applied to an in-memory copy. Nothing here writes to
docs/PUBLIC_PROOF_SURFACE.yaml or docs/PORTFOLIO_CAPABILITIES.yaml.

Hermetic: no network, no model, no database. Route checking imports the real
Starlette app and asks the real router, which is in-process.
"""

from __future__ import annotations

import copy
import unittest

import proof_registry as pr


def _problem_text(problems) -> str:
    return "\n".join(problems)


class RealSurfacePassesTestCase(unittest.TestCase):
    def setUp(self):
        self.surface = pr.load_surface()
        self.capabilities = pr.load_capabilities()

    def test_the_real_public_proof_surface_is_valid(self):
        problems = pr.validate(self.surface, self.capabilities)
        self.assertEqual(
            problems, [],
            "the public proof surface would misrepresent the evidence:\n"
            + _problem_text(problems),
        )

    def test_the_front_door_is_within_the_agreed_range(self):
        primary = [e for e in self.surface["capabilities"] if e["tier"] == "PRIMARY"]
        self.assertGreaterEqual(len(primary), pr.MIN_PRIMARY)
        self.assertLessEqual(len(primary), pr.MAX_PRIMARY)

    def test_every_audience_route_has_something_to_show(self):
        """A route offered to a visitor that resolves to an empty list is a
        dead end, and a dead end on the front door is worse than no route."""
        for audience in self.surface["audiences"]:
            matching = [
                e for e in self.surface["capabilities"]
                if audience in (e.get("audiences") or [])
            ]
            self.assertGreater(
                len(matching), 0,
                f"audience route {audience!r} has no capabilities mapped to it",
            )

    def test_the_paused_experiment_is_present_and_is_not_presented_as_live(self):
        """Specifically guarded because this is the single claim on the surface
        most likely to be quietly upgraded later: it is the most impressive
        engineering on the page and its product thesis failed."""
        paused = [
            e for e in self.surface["capabilities"]
            if e["capability_id"] == "falsification-preregistered-negative-result"
        ]
        self.assertEqual(len(paused), 1, "the Deep Consensus case study left the surface")
        entry = paused[0]
        self.assertEqual(entry["public_status"], "EXPERIMENTAL_PAUSED")
        limitation = entry["public_limitation"].lower()
        self.assertIn("paused", limitation)
        self.assertIn("unproven", limitation)

    def test_no_live_status_sits_above_its_recorded_verification_level(self):
        for entry in self.surface["capabilities"]:
            if entry["public_status"] != "LIVE_VERIFIED":
                continue
            level = self.capabilities[entry["capability_id"]]["verification_level"]
            self.assertEqual(
                level, "PRODUCTION_VERIFIED",
                f"{entry['capability_id']} is published as LIVE but is only {level}",
            )


class SeededMutationTestCase(unittest.TestCase):
    """Each test removes or corrupts exactly one thing and asserts the gate
    says so. The control test proves the copy itself is clean, without which a
    later failure would prove nothing."""

    def setUp(self):
        self.surface = copy.deepcopy(pr.load_surface())
        self.capabilities = copy.deepcopy(pr.load_capabilities())
        self.routes = pr._registered_get_paths()

    def _validate(self):
        return pr.validate(self.surface, self.capabilities, routes=self.routes)

    def _first(self):
        return self.surface["capabilities"][0]

    def test_control_the_unmutated_copy_passes(self):
        self.assertEqual(self._validate(), [])

    # --- check 1: a claim with no registered capability behind it ----------
    def test_an_unknown_capability_id_is_detected(self):
        self._first()["capability_id"] = "a-capability-that-was-never-built"
        self.assertIn("does not exist in docs/PORTFOLIO_CAPABILITIES.yaml", _problem_text(self._validate()))

    # --- check 2: duplicates ----------------------------------------------
    def test_a_duplicate_capability_id_is_detected(self):
        self.surface["capabilities"].append(copy.deepcopy(self._first()))
        self.assertIn("duplicate capability_id", _problem_text(self._validate()))

    # --- check 3: invalid status -------------------------------------------
    def test_an_invented_status_is_detected(self):
        self._first()["public_status"] = "FULLY_PRODUCTION_GRADE"
        self.assertIn("is not in the published status_vocabulary", _problem_text(self._validate()))

    # --- check 4: THE important one. A claim presented above its evidence --
    def test_presenting_a_tested_only_capability_as_live_is_detected(self):
        """The exact failure this gate exists to stop: the paused research
        result, whose recorded level is TESTED, relabelled as LIVE."""
        for entry in self.surface["capabilities"]:
            if entry["capability_id"] == "falsification-preregistered-negative-result":
                entry["public_status"] = "LIVE_VERIFIED"
        text = _problem_text(self._validate())
        self.assertIn("this is a claim presented above its evidence", text)

    def test_downgrading_a_registry_level_invalidates_a_live_claim(self):
        """The mutation from the other direction: the claim is untouched and the
        underlying evidence weakens. The surface must not stay silently valid."""
        cid = self._first()["capability_id"]
        self.capabilities[cid]["verification_level"] = "IMPLEMENTED"
        self.assertIn("presented above its evidence", _problem_text(self._validate()))

    # --- check 5: a missing limitation ------------------------------------
    def test_a_missing_limitation_is_detected(self):
        del self._first()["public_limitation"]
        self.assertIn("required field 'public_limitation' is missing", _problem_text(self._validate()))

    def test_an_empty_claim_is_detected(self):
        self._first()["public_claim"] = "   "
        self.assertIn("required field 'public_claim' is missing or empty", _problem_text(self._validate()))

    # --- check 6/7: destinations -------------------------------------------
    def test_a_capability_with_no_destination_is_detected(self):
        self._first()["destinations"] = []
        self.assertIn("needs at least one inspectable destination", _problem_text(self._validate()))

    def test_an_unregistered_internal_route_is_detected(self):
        self._first()["destinations"] = [{"label": "Nowhere", "href": "/proof-of-nothing"}]
        self.assertIn("is not a registered route", _problem_text(self._validate()))

    def test_a_bare_relative_path_is_detected(self):
        self._first()["destinations"] = [{"label": "Oops", "href": "workbench"}]
        self.assertIn("is a bare relative path", _problem_text(self._validate()))

    def test_a_destination_with_no_href_is_detected(self):
        self._first()["destinations"] = [{"label": "Dangling"}]
        self.assertIn("has no href", _problem_text(self._validate()))

    # --- check 9: private leakage through a destination --------------------
    def test_a_destination_pointing_at_a_private_surface_is_detected(self):
        self._first()["destinations"] = [{"label": "Internal", "href": "/control-plane"}]
        self.assertIn("FORBIDDEN/PRIVATE", _problem_text(self._validate()))

    def test_a_destination_pointing_at_the_private_context_repo_is_detected(self):
        self._first()["destinations"] = [
            {"label": "Strategy", "href": "https://github.com/karthikdevadoss/karthik-ai-context"}
        ]
        self.assertIn("FORBIDDEN/PRIVATE", _problem_text(self._validate()))

    # --- check 10: evidence that moved ------------------------------------
    def test_evidence_that_no_longer_exists_on_disk_is_detected(self):
        cid = self._first()["capability_id"]
        self.capabilities[cid]["relevant_modules"] = ["agent/a_module_that_was_deleted.py"]
        self.assertIn("does not exist on disk", _problem_text(self._validate()))

    # --- check 11: paused presented without saying so ---------------------
    def test_a_paused_experiment_whose_limitation_omits_paused_is_detected(self):
        for entry in self.surface["capabilities"]:
            if entry["public_status"] == "EXPERIMENTAL_PAUSED":
                entry["public_limitation"] = "An ambitious multi-model research programme."
        self.assertIn("paused research must not read as working product", _problem_text(self._validate()))

    # --- check 12: audiences ----------------------------------------------
    def test_an_unknown_audience_is_detected(self):
        self._first()["audiences"] = ["venture_capitalists"]
        self.assertIn("is not one of", _problem_text(self._validate()))

    def test_no_audience_at_all_is_detected(self):
        self._first()["audiences"] = []
        self.assertIn("needs at least one audience", _problem_text(self._validate()))

    # --- check 13: front-door size ----------------------------------------
    def test_too_many_front_door_capabilities_is_detected(self):
        for entry in self.surface["capabilities"]:
            entry["tier"] = "PRIMARY"
        self.assertIn("floods the first screen", _problem_text(self._validate()))

    def test_too_few_front_door_capabilities_is_detected(self):
        for entry in self.surface["capabilities"]:
            entry["tier"] = "SECONDARY"
        self.assertIn("a front door needs at least", _problem_text(self._validate()))

    # --- the validator must not crash on the thing it validates -----------
    def test_a_malformed_surface_is_reported_not_raised(self):
        problems = pr.validate("not a mapping at all", self.capabilities, routes=self.routes)
        self.assertTrue(problems)

    def test_an_empty_surface_is_reported_not_raised(self):
        problems = pr.validate({}, self.capabilities, routes=self.routes)
        self.assertIn("there is no proof surface", _problem_text(problems))

    def test_removing_status_requires_is_itself_reported(self):
        """Deleting the honesty constraint must not read as 'nothing to check'."""
        del self.surface["status_requires"]
        self.assertIn("nothing stops a status being overstated", _problem_text(self._validate()))


class RouteClassifierTestCase(unittest.TestCase):
    """The classifier underneath check 7, tested directly against the real
    router -- including a parameterised route, which is exactly where a
    hand-rolled string comparison would have disagreed with Starlette."""

    def setUp(self):
        self.routes = pr._registered_get_paths()

    def test_a_real_registered_route_is_valid(self):
        self.assertEqual(pr.classify_href("/workbench", self.routes), "VALID_INTERNAL_ROUTE")

    def test_a_real_parameterised_route_is_valid(self):
        self.assertEqual(
            pr.classify_href("/showcase/senior-java-ai-transformation", self.routes),
            "VALID_INTERNAL_ROUTE",
        )

    def test_an_unregistered_route_is_broken(self):
        self.assertEqual(pr.classify_href("/not-a-page", self.routes), "BROKEN_INTERNAL_ROUTE")

    def test_an_absolute_url_is_external(self):
        self.assertEqual(pr.classify_href("https://example.com/x", self.routes), "ABSOLUTE_EXTERNAL")

    def test_a_bare_relative_path_is_its_own_class(self):
        self.assertEqual(pr.classify_href("usage", self.routes), "BARE_RELATIVE_PATH")


class PublicEntriesTestCase(unittest.TestCase):
    def test_public_entries_returns_the_front_door(self):
        primary = pr.public_entries(tier="PRIMARY")
        self.assertGreaterEqual(len(primary), pr.MIN_PRIMARY)
        self.assertTrue(all(e["tier"] == "PRIMARY" for e in primary))

    def test_public_entries_filters_by_audience(self):
        for audience in ("recruiter", "ai_hiring_manager", "backend_interviewer"):
            entries = pr.public_entries(audience=audience)
            self.assertGreater(len(entries), 0, f"no entries for {audience}")
            self.assertTrue(all(audience in e["audiences"] for e in entries))


if __name__ == "__main__":
    unittest.main()


class GeneratedArtifactsMatchTheRegistryTestCase(unittest.TestCase):
    """Generation only prevents drift if regenerating is enforced.

    Without this, agent/web/home.html and agent/web/proof.html could be
    hand-edited and the registry would quietly stop being the source of truth
    -- which is exactly the state this sprint set out to end. A hand-edit is a
    build failure, by design.
    """

    def test_generated_pages_are_in_step_with_the_registry(self):
        import build_proof_surface as bps

        stale = []
        for path, intended in bps.build().items():
            on_disk = path.read_text(encoding="utf-8") if path.exists() else None
            if on_disk is None:
                stale.append(f"{path.name} does not exist")
            elif on_disk.replace("\r\n", "\n") != intended.replace("\r\n", "\n"):
                stale.append(f"{path.name} differs from what the registry renders")
        self.assertEqual(
            stale, [],
            "generated proof surface is stale or was hand-edited:\n  "
            + "\n  ".join(stale)
            + "\n\nRun: python agent/build_proof_surface.py --write",
        )

    def test_the_splicer_refuses_a_file_with_no_markers(self):
        """A renderer that cannot find its own fence must refuse, not append --
        appending would corrupt the page it maintains."""
        import build_proof_surface as bps

        with self.assertRaises(ValueError):
            bps.splice_home("<html>no markers here</html>", "rows")

    def test_the_splicer_refuses_duplicated_markers(self):
        import build_proof_surface as bps

        doubled = f"{bps.START}{bps.END}{bps.START}{bps.END}"
        with self.assertRaises(ValueError):
            bps.splice_home(doubled, "rows")

    def test_generation_refuses_an_invalid_registry(self):
        """The render path must not be able to publish a surface the gate would
        refuse. Checked by making the in-memory surface invalid."""
        import build_proof_surface as bps
        from unittest.mock import patch

        broken = copy.deepcopy(pr.load_surface())
        broken["capabilities"][0]["public_limitation"] = ""
        with patch.object(pr, "load_surface", return_value=broken):
            with self.assertRaises(ValueError):
                bps.build()


class ShortLimitationMutationTestCase(unittest.TestCase):
    """Sprint 18 release closure: /proof collapses each capability, and the
    COLLAPSED card shows only limitation_short. That makes the short form the
    text most visitors actually read, so it gets the same seeded-mutation
    treatment as every other check here."""

    def setUp(self):
        self.surface = copy.deepcopy(pr.load_surface())
        self.capabilities = copy.deepcopy(pr.load_capabilities())
        self.routes = pr._registered_get_paths()

    def _problems(self):
        return "\n".join(pr.validate(self.surface, self.capabilities, routes=self.routes))

    def _first(self):
        return self.surface["capabilities"][0]

    def test_control_the_unmutated_copy_passes(self):
        self.assertEqual(pr.validate(self.surface, self.capabilities, routes=self.routes), [])

    def test_a_missing_short_limitation_is_detected(self):
        del self._first()["limitation_short"]
        self.assertIn("required field 'limitation_short' is missing", self._problems())

    def test_an_overlong_short_limitation_is_detected(self):
        self._first()["limitation_short"] = "x" * (pr.MAX_SHORT_LIMITATION + 1)
        self.assertIn("it has to fit a collapsed card", self._problems())

    def test_a_trivially_short_limitation_is_detected(self):
        self._first()["limitation_short"] = "Some limits."
        self.assertIn("a boundary that short is decoration", self._problems())

    def test_a_short_limitation_copied_verbatim_from_the_long_one_is_detected(self):
        entry = self._first()
        entry["limitation_short"] = " ".join(entry["public_limitation"].split())
        self.assertIn("nothing was actually compressed", self._problems())

    def test_a_paused_experiment_whose_SHORT_limitation_omits_paused_is_detected(self):
        """The most dangerous single mutation on this page: the collapsed card
        is the only thing many readers see, so a paused experiment whose SHORT
        limitation reads like a finished product is a real misrepresentation
        even while the full limitation underneath is still honest."""
        for entry in self.surface["capabilities"]:
            if entry["public_status"] == "EXPERIMENTAL_PAUSED":
                entry["limitation_short"] = "A multi-model verification engine with strong engineering."
        problems = self._problems()
        self.assertIn("limitation_short never says", problems)
        self.assertIn("the collapsed card shows only the short form", problems)

    def test_every_real_short_limitation_is_within_bounds(self):
        for entry in self.surface["capabilities"]:
            short = entry["limitation_short"]
            with self.subTest(capability=entry["capability_id"]):
                self.assertLessEqual(len(short), pr.MAX_SHORT_LIMITATION)
                self.assertGreaterEqual(len(short), pr.MIN_SHORT_LIMITATION)
