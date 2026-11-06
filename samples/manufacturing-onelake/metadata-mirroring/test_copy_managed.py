import unittest

from copy_managed import create_sql, identifier, signature, validate_location


class ManagedCopyTests(unittest.TestCase):
    def test_identifier_quoting(self):
        self.assertEqual(identifier("a`b"), "`a``b`")
        with self.assertRaises(ValueError):
            identifier("bad\nname")

    def test_preserves_schema_and_uses_managed_storage(self):
        table = {"name": "products", "columns": [
            {"name": "product_id", "type_text": "int", "nullable": False},
            {"name": "unit_price", "type_text": "decimal(12,2)", "nullable": False},
            {"name": "label", "type_text": "string", "nullable": True},
        ]}
        create, insert = create_sql("`foreign`.`s`.`products`", "`native`.`s`.`products`", table)
        self.assertIn("`unit_price` DECIMAL(12,2) NOT NULL", create)
        self.assertIn("`product_id` INT NOT NULL", create)
        self.assertNotIn("`label` STRING NOT NULL", create)
        self.assertNotIn("LOCATION", create)
        self.assertNotIn("REPLACE", create)
        self.assertIn("SELECT `product_id`, `unit_price`, `label` FROM `foreign`", insert)
        self.assertEqual(signature(table)[1], ("unit_price", "decimal(12,2)", False))

    def test_unknown_type_is_explicit_error(self):
        with self.assertRaisesRegex(ValueError, "Unsupported source type"):
            create_sql("source", "target", {"name": "t", "columns": [
                {"name": "value", "type_text": "malicious; SQL", "nullable": True},
            ]})

    def test_rejects_onelake_and_external_destinations(self):
        source = {"storage_location": "abfss://source@onelake.dfs.fabric.microsoft.com/item"}
        target = {"storage_location": source["storage_location"], "full_name": "native.s.t",
                  "table_type": "MANAGED", "data_source_format": "DELTA"}
        with self.assertRaises(ValueError):
            validate_location(source, target)
        target["storage_location"] = "abfss://container@storage.dfs.core.windows.net/path"
        validate_location(source, target)
        target["table_type"] = "EXTERNAL"
        with self.assertRaises(ValueError):
            validate_location(source, target)


if __name__ == "__main__":
    unittest.main()
