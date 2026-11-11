import copy
import json
import unittest

from manage_agent import CONNECTION_NAME, FABRIC_URL
from verify_agent import compare_data, validate_binding, validate_response


class VerificationTests(unittest.TestCase):
    def response(self, data: object) -> dict:
        return {
            "id": "test-response",
            "status": "completed",
            "output": [
                {
                    "type": "mcp_call", "server_label": "ge_vernova_fleet",
                    "name": "query", "status": "completed", "output": "queried synthetic fleet",
                },
                {
                    "type": "message",
                    "content": [{
                        "type": "output_text",
                        "text": json.dumps({"source": "GE Vernova Fleet Advisor synthetic data", "data": data}),
                    }],
                },
            ],
        }

    def test_exact_values_and_tool_evidence(self) -> None:
        self.assertEqual(validate_response(self.response({"mwh": 12}), {"mwh": 12})["responseId"], "test-response")
        with self.assertRaisesRegex(ValueError, "expected 12"):
            validate_response(self.response({"mwh": 13}), {"mwh": 12})
        for change in ("missing", "wrong-server", "unauthorized"):
            response = copy.deepcopy(self.response({"mwh": 12}))
            if change == "missing":
                response["output"].pop(0)
            elif change == "wrong-server":
                response["output"][0]["server_label"] = "other"
            else:
                response["output"][0]["error"] = {"code": "unauthorized"}
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_response(response, {"mwh": 12})

    def test_shape_order_and_number_validation(self) -> None:
        expected = [{"name": "A", "hours": 8}, {"name": "B", "hours": 7}]
        for actual in (list(reversed(expected)), expected[:1], [{"name": "A", "hours": 8, "extra": 0}]):
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                compare_data(actual, expected)
        for actual in (True, "1", float("nan"), float("inf")):
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                compare_data(actual, 1)

    def test_six_decimal_percentage_precision(self) -> None:
        compare_data({"site": 60.111869}, {"site": 60.111869})
        with self.assertRaises(ValueError):
            compare_data({"site": 60.111868}, {"site": 60.111869})
        with self.assertRaises(ValueError):
            compare_data({"site": 0.60111869}, {"site": 60.111869})

    def test_saved_binding_not_just_url_in_instructions(self) -> None:
        definition = {
            "kind": "prompt",
            "instructions": FABRIC_URL,
            "tools": [{
                "type": "fabric_iq_preview", "server_label": "ge_vernova_fleet",
                "server_url": FABRIC_URL,
                "project_connection_id": "/project/connections/" + CONNECTION_NAME,
            }],
        }
        saved = {"versions": {"latest": {"definition": definition}}}
        validate_binding(saved)
        definition["tools"][0]["server_url"] = "https://example.invalid"
        with self.assertRaisesRegex(ValueError, "binding"):
            validate_binding(saved)


if __name__ == "__main__":
    unittest.main()
