import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
backend_path = str(BACKEND_DIR)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from core.pipeline.state_machine import _coerce_json_container


class PipelineStateMachineCoercionTestCase(unittest.TestCase):
    def test_coerces_serialized_dict_payload(self):
        payload = _coerce_json_container('{"layer0": {"ok": true}}', dict, {})
        self.assertEqual(payload, {"layer0": {"ok": True}})

    def test_coerces_serialized_list_payload(self):
        payload = _coerce_json_container('[{"status": "completed"}]', list, [])
        self.assertEqual(payload, [{"status": "completed"}])

    def test_returns_default_for_invalid_payload(self):
        payload = _coerce_json_container("not-json", dict, {})
        self.assertEqual(payload, {})


if __name__ == "__main__":
    unittest.main()
