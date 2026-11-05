import copy
import unittest
from decimal import Decimal

from sample_data import EXPECTED_COUNTS, generate, summary, validate


class CustomerOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = generate()

    def test_exact_counts_and_determinism(self):
        self.assertEqual(sum(EXPECTED_COUNTS.values()), 9323)
        self.assertEqual(self.data, generate())
        self.assertNotEqual(self.data["sales_order_lines"], generate(43)["sales_order_lines"])
        validate(self.data)

    def test_statuses_and_decimal_amounts(self):
        result = summary(self.data)
        self.assertEqual(result["order_statuses"], {
            "fulfilled": 600, "open": 200, "partially_fulfilled": 200,
        })
        self.assertTrue(all(
            isinstance(row["line_amount"], Decimal)
            for row in self.data["sales_order_lines"]
        ))

    def reject(self, table, column, value, pattern, index=0):
        data = copy.deepcopy(self.data)
        data[table][index][column] = value
        with self.assertRaisesRegex(ValueError, pattern):
            validate(data)

    def test_duplicate_primary_key(self):
        self.reject("customers", "customer_id", 1, "primary key", index=1)

    def test_bad_foreign_key(self):
        self.reject("sales_orders", "customer_id", -1, "foreign key")

    def test_bad_line_amount(self):
        self.reject("sales_order_lines", "line_amount", Decimal("0.00"), "amount")

    def test_bad_types(self):
        self.reject("products", "unit_price", 12.34, "type or value")

    def test_bad_work_quantity(self):
        self.reject("work_orders", "produced_quantity", 100000, "quantities")

    def test_bad_shipment_quantity(self):
        self.reject("shipment_lines", "shipped_quantity", 100000, "shipped quantity")

    def test_shipment_cannot_reference_another_order(self):
        self.reject("shipment_lines", "order_line_id", 4, "mismatch")

    def test_order_status_matches_shipments(self):
        self.reject("sales_orders", "status", "open", "fulfillment")

    def test_bad_dates(self):
        from datetime import date
        self.reject("shipments", "delivery_date", date(2026, 1, 1), "dates")


if __name__ == "__main__":
    unittest.main()
