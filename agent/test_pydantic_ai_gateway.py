"""Pydantic AI slice: fake model only, no live Anthropic calls. Proves typed
output is parsed, invalid output is rejected, and every billed call goes
through reasoning_gateway.call() (purpose gate, LLM_MODE=DISABLED kill switch)."""
import json
import os
import unittest
from unittest.mock import MagicMock, patch

import pydantic_ai_gateway as pag
import reasoning_gateway
import triage_execution as te

GOOD = {"hypothesis": "h", "root_cause": "r", "affected_component": "c", "confidence": "HIGH"}


def _create_fn(text):
    block = MagicMock(); block.type = "text"; block.text = text
    resp = MagicMock(); resp.content = [block]; resp.usage = None
    return MagicMock(return_value=resp)


def _run(create_fn, purpose="NOVEL_ROOT_CAUSE_HYPOTHESES"):
    return pag.run_typed_diagnosis("SYS", "EVIDENCE", purpose=purpose, max_tokens=64,
                                   api_key=None, create_fn=create_fn)


class TypedOutputTests(unittest.TestCase):
    def test_valid_output_is_parsed_into_typed_model(self):
        diagnosis, usage = _run(_create_fn(json.dumps(GOOD)))
        self.assertIsInstance(diagnosis, pag.Diagnosis)
        self.assertEqual(diagnosis.confidence, "HIGH")
        self.assertIsNone(usage)

    def test_markdown_fenced_json_is_still_parsed(self):
        diagnosis, _ = _run(_create_fn("```json\n" + json.dumps(GOOD) + "\n```"))
        self.assertEqual(diagnosis.hypothesis, "h")

    def test_schema_violation_is_rejected_not_passed_through(self):
        for bad in ({**GOOD, "confidence": "CERTAIN"}, {"hypothesis": "only"}, "not json at all"):
            with self.subTest(bad=bad):
                text = bad if isinstance(bad, str) else json.dumps(bad)
                cf = _create_fn(text)
                with self.assertRaises(pag.UnexpectedModelBehavior):
                    _run(cf)
                self.assertEqual(cf.call_count, 1, "no second billed retry on bad output")

    def test_schema_is_injected_into_the_system_prompt(self):
        cf = _create_fn(json.dumps(GOOD))
        _run(cf)
        system = cf.call_args.kwargs["system"]
        self.assertTrue(system.startswith("SYS"))
        self.assertIn("affected_component", system)
        self.assertEqual(cf.call_args.kwargs["messages"], [{"role": "user", "content": "EVIDENCE"}])


class GatewayRoutingTests(unittest.TestCase):
    def test_call_goes_through_reasoning_gateway_call(self):
        with patch.object(reasoning_gateway, "call", wraps=reasoning_gateway.call) as spy:
            _run(_create_fn(json.dumps(GOOD)))
        spy.assert_called_once()
        self.assertEqual(spy.call_args.kwargs["purpose"], "NOVEL_ROOT_CAUSE_HYPOTHESES")
        self.assertIn(spy.call_args.kwargs["purpose"], reasoning_gateway.ADVISORY_PURPOSES)

    def test_non_advisory_purpose_is_denied_before_any_provider_call(self):
        cf = _create_fn(json.dumps(GOOD))
        with self.assertRaises(pag.GatewayDenied) as ctx:
            _run(cf, purpose="NOT_A_REAL_PURPOSE")
        self.assertIn("ADVISORY_PURPOSES", ctx.exception.reason)
        cf.assert_not_called()

    def test_llm_mode_disabled_makes_no_provider_call(self):
        cf = _create_fn(json.dumps(GOOD))
        with patch.dict(os.environ, {"LLM_MODE": "DISABLED"}):
            with self.assertRaises(pag.GatewayDenied) as ctx:
                _run(cf)
        self.assertIn("LLM_MODE=DISABLED", ctx.exception.reason)
        cf.assert_not_called()


class TriageDiagnoseWiringTests(unittest.TestCase):
    def test_diagnose_returns_typed_fields_and_goes_through_gateway(self):
        with patch.object(reasoning_gateway, "call", wraps=reasoning_gateway.call) as spy:
            result = te.diagnose({"defectReproduced": True}, create_fn=_create_fn(json.dumps(GOOD)))
        spy.assert_called_once()
        self.assertTrue(result["model_called"])
        self.assertEqual({k: result[k] for k in GOOD}, GOOD)

    def test_diagnose_rejects_schema_invalid_output_honestly(self):
        result = te.diagnose({}, create_fn=_create_fn(json.dumps({**GOOD, "confidence": "CERTAIN"})))
        self.assertTrue(result["model_called"])
        self.assertIsNone(result["hypothesis"])
        self.assertIn("typed Diagnosis schema", result["explanation"])

    def test_diagnose_disabled_mode_makes_no_provider_call(self):
        cf = _create_fn(json.dumps(GOOD))
        with patch.dict(os.environ, {"LLM_MODE": "DISABLED"}):
            result = te.diagnose({}, create_fn=cf)
        self.assertFalse(result["model_called"])
        self.assertIn("LLM_MODE=DISABLED", result["explanation"])
        cf.assert_not_called()


if __name__ == "__main__":
    unittest.main()
