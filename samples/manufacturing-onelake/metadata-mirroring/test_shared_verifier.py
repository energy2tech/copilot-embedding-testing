import unittest

from copy_managed import canonical
from verify_shared_data import validation_queries


class SharedVerifierTests(unittest.TestCase):
    def test_existing_default_queries_are_preserved(self):
        fabric, databricks = validation_queries("contoso_mfg_onelake", "manufacturing_demo")
        self.assertEqual(len(fabric), 8)
        self.assertEqual(len(databricks), 8)
        self.assertIn("manufacturing_demo.customers", fabric[0])
        self.assertIn("contoso_mfg_onelake.manufacturing_demo.customers", databricks[0])

    def test_managed_catalog_and_all_table_rows(self):
        fabric, databricks = validation_queries(
            "dbw_contoso_mfg_demo_eus2", "manufacturing_managed_demo", True)
        self.assertEqual(len(fabric), 16)
        self.assertEqual(len(databricks), 16)
        self.assertIn("manufacturing_managed_demo.customers", fabric[0])
        self.assertIn("dbw_contoso_mfg_demo_eus2.manufacturing_managed_demo.customers", databricks[0])
        self.assertEqual(fabric[8], "SELECT * FROM manufacturing_managed_demo.customers")

    def test_invalid_identifiers_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "SQL identifiers"):
            validation_queries("catalog; DROP TABLE t", "schema")

    def test_row_comparison_retains_duplicates_and_exact_decimal_values(self):
        self.assertEqual(canonical([["1", "27.00"], ["2", "12.30"]]),
                         canonical([[2, "12.3"], [1, 27]]))
        self.assertNotEqual(canonical([["1"], ["1"]]), canonical([["1"]]))


if __name__ == "__main__":
    unittest.main()
