import json
import unittest
from pathlib import Path

from sample_data import EXPECTED_COUNTS, SCHEMAS, fingerprint, generate, validate


class ManufacturingDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = generate()

    def test_exact_counts_and_invariants(self):
        validate(self.tables)
        self.assertEqual(sum(EXPECTED_COUNTS.values()), 100089)
        self.assertEqual(set(SCHEMAS), set(self.tables._fields))
        for name, rows in self.tables._asdict().items():
            columns = [column.strip().split()[0] for column in SCHEMAS[name].split(",")]
            self.assertEqual(columns, list(rows[0]._fields), name)

    def test_deterministic_generation(self):
        self.assertEqual(fingerprint(self.tables), fingerprint(generate()))
        self.assertNotEqual(fingerprint(self.tables), fingerprint(generate(43)))

    def test_fixed_dates_and_failure_examples(self):
        dates = self.tables.dim_date
        self.assertEqual(str(dates[0].calendar_date), "2026-07-01")
        self.assertEqual(str(dates[-1].calendar_date), "2026-09-28")
        self.assertEqual((dates[-1].calendar_date - dates[0].calendar_date).days, 89)
        self.assertTrue(any(row.scrap_units > 0 for row in self.tables.fact_production))
        self.assertTrue(any(not row.passed for row in self.tables.fact_quality_inspection))
        self.assertTrue(any(row.passed for row in self.tables.fact_quality_inspection))

    def test_invalid_quantity_is_rejected(self):
        rows = self.tables.fact_production.copy()
        rows[0] = rows[0]._replace(good_units=rows[0].total_units + 1)
        with self.assertRaisesRegex(ValueError, "quantities"):
            validate(self.tables._replace(fact_production=rows))

    def test_invalid_foreign_key_is_rejected(self):
        rows = self.tables.fact_work_order.copy()
        rows[0] = rows[0]._replace(product_id=-1)
        with self.assertRaisesRegex(ValueError, "dimension"):
            validate(self.tables._replace(fact_work_order=rows))

    def test_overlap_is_rejected(self):
        rows = self.tables.fact_downtime.copy()
        rows[1] = rows[1]._replace(start_utc=rows[0].start_utc, end_utc=rows[0].end_utc)
        with self.assertRaisesRegex(ValueError, "Overlapping"):
            validate(self.tables._replace(fact_downtime=rows))

    def test_inspection_flag_is_checked(self):
        rows = self.tables.fact_quality_inspection.copy()
        rows[0] = rows[0]._replace(passed=not rows[0].passed)
        with self.assertRaisesRegex(ValueError, "pass flag"):
            validate(self.tables._replace(fact_quality_inspection=rows))


class InfrastructureScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        template_path = Path(__file__).parent / "infra" / "main.json"
        cls.template = json.loads(template_path.read_text(encoding="utf-8"))
        cls.resources = cls.template["resources"][1]["properties"]["template"]["resources"]

    def test_only_approved_resource_types(self):
        self.assertEqual(
            [resource["type"] for resource in self.template["resources"]],
            ["Microsoft.Resources/resourceGroups", "Microsoft.Resources/deployments"],
        )
        self.assertEqual(
            {resource["type"] for resource in self.resources},
            {"Microsoft.Databricks/workspaces", "Microsoft.Databricks/accessConnectors"},
        )
        self.assertEqual(len(self.resources), 2)
        self.assertEqual(self.template["resources"][1]["properties"]["mode"], "Incremental")

    def test_premium_secure_connectivity_and_managed_identity(self):
        workspace, connector = self.resources
        self.assertEqual(workspace["sku"]["name"], "premium")
        self.assertTrue(workspace["properties"]["parameters"]["enableNoPublicIp"]["value"])
        self.assertEqual(connector["identity"], {"type": "SystemAssigned"})


if __name__ == "__main__":
    unittest.main()
