"""BL-041: the config-drift gate must detect a key present in one Spring
profile file but missing from another (the class of the Owner's real
Sep-2025 NRG incident: a CMS URL that worked in stage because prod carried
different yml values). Observed failing first (module absent -> ImportError)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_config_drift  # noqa: E402


def _write(root, name, text):
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, name), "w", encoding="utf-8") as f:
        f.write(text)


class ConfigDriftDetectionTestCase(unittest.TestCase):

    def test_key_present_in_stage_but_missing_in_prod_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "application.properties", "server.port=8080\n")
            _write(tmp, "application-stage.properties",
                   "downstream.cms.url=http://stg-cms/api\ndownstream.billing.url=http://stg-billing\n")
            _write(tmp, "application-prod.properties", "downstream.billing.url=http://billing\n")

            drift = check_config_drift.detect_drift(tmp, allowlist=[])

            keys = {(d["key"], tuple(sorted(d["missing_from"]))) for d in drift}
            self.assertIn(("downstream.cms.url", ("application-prod.properties",)), keys)
            self.assertEqual(len(drift), 1, drift)

    def test_yaml_profiles_are_flattened_and_compared_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "application.yml", "server:\n  port: 8080\n")
            _write(tmp, "application-stage.yml", "nrg:\n  spec:\n    profile: http://stg\n    billing: http://stg-b\n")
            _write(tmp, "application-prod.yml", "nrg:\n  spec:\n    profile: http://prod\n")

            drift = check_config_drift.detect_drift(tmp, allowlist=[])

            self.assertEqual([d["key"] for d in drift], ["nrg.spec.billing"])

    def test_allowlisted_profile_specific_key_is_not_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "application-stage.properties", "debug.stage.only=true\n")
            _write(tmp, "application-prod.properties", "x=1\n")

            # "x" (prod-only, not allowlisted) is still drift; only the allowlisted key disappears
            self.assertEqual([d["key"] for d in check_config_drift.detect_drift(tmp, allowlist=["debug.stage.only"])], ["x"])
            self.assertEqual(len(check_config_drift.detect_drift(tmp, allowlist=[])), 2)

    def test_single_profile_file_cannot_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "application.properties", "a=1\n")
            _write(tmp, "application-stage.properties", "b=2\n")
            self.assertEqual(check_config_drift.detect_drift(tmp, allowlist=[]), [])


if __name__ == "__main__":
    unittest.main()
