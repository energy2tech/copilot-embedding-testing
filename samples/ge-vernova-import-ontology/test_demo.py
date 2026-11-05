import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from build_demo import NAME, build, expected_answers, generate, validate
from verify_model import compare


class FleetDataTests(unittest.TestCase):
    def test_counts_keys_and_integrity(self):
        tables = generate()
        validate(tables)
        self.assertEqual([len(rows) for rows in tables.values()], [6, 24, 90, 2160, 72])
        self.assertEqual(len({(r["TurbineId"], r["DateKey"]) for r in tables["Daily Generation"]}), 2160)
        self.assertEqual(tables["Date"][0]["Date"], "2026-01-01")
        self.assertEqual(tables["Date"][-1]["Date"], "2026-03-31")

    def test_determinism(self):
        self.assertEqual(generate(), generate())

    def test_invalid_data_is_rejected(self):
        mutations = [
            ("Turbine", 0, "SiteId", -1, "foreign key"),
            ("Daily Generation", 0, "TurbineId", -1, "foreign key"),
            ("Daily Generation", 0, "Downtime Hours", 25, "downtime"),
            ("Daily Generation", 0, "Generation MWh", -1, "generation"),
            ("Maintenance Event", 0, "Cost USD", -1, "cost"),
        ]
        for table, index, key, value, message in mutations:
            with self.subTest(key=key):
                tables = copy.deepcopy(generate())
                tables[table][index][key] = value
                with self.assertRaisesRegex(ValueError, message):
                    validate(tables)

    def test_adjustment_changes_only_one_generation_row(self):
        baseline = generate()
        changed = generate(10)
        self.assertEqual(changed["Daily Generation"][0]["Generation MWh"],
                         baseline["Daily Generation"][0]["Generation MWh"] + 10)
        self.assertEqual(changed["Daily Generation"][1:], baseline["Daily Generation"][1:])
        old, new = expected_answers(baseline), expected_answers(changed)
        self.assertEqual(new["fleet"]["Total Generation MWh"], old["fleet"]["Total Generation MWh"] + 10)
        self.assertEqual(new["maintenance_by_site"], old["maintenance_by_site"])
        self.assertEqual(new["fleet"]["Downtime Hours"], old["fleet"]["Downtime Hours"])
        with self.assertRaisesRegex(ValueError, "adjustment"):
            generate(101)

    def test_capacity_factor_bounds(self):
        result = expected_answers(generate())
        self.assertTrue(all(0 < value < 1 for value in result["capacity_factor_by_site"].values()))
        self.assertEqual(sum(r["Maintenance Event Count"] for r in result["maintenance_by_site"].values()), 72)


class ProjectTests(unittest.TestCase):
    def test_complete_portable_project(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            build(project)
            entry = json.loads((project / f"{NAME}.pbip").read_text())
            report = project / entry["artifacts"][0]["report"]["path"]
            binding = json.loads((report / "definition.pbir").read_text())
            model = report / binding["datasetReference"]["byPath"]["path"]
            self.assertTrue((model / "definition.pbism").is_file())
            self.assertTrue((model / "definition" / "database.tmdl").is_file())
            self.assertEqual(len(list((model / "definition" / "tables").glob("*.tmdl"))), 5)
            for table in (model / "definition" / "tables").glob("*.tmdl"):
                text = table.read_text()
                self.assertEqual(text.count("mode: import"), 1)
                self.assertNotIn("File.Contents", text)
                self.assertNotIn("Web.Contents", text)
                self.assertNotIn("directLake", text)
                self.assertNotIn("directQuery", text)
                columns = set(re.findall(r"^\tcolumn '([^']+)'", text, re.MULTILINE))
                measures = set(re.findall(r"^\tmeasure '([^']+)'", text, re.MULTILINE))
                self.assertFalse(columns & measures, "Columns and measures must have distinct names")
                self.assertNotRegex(text, r"sourceColumn: '")
                if table.stem == "Date":
                    self.assertIn("sourceColumn: Date\n\n\t\tannotation", text)
            pages = json.loads((report / "definition" / "pages" / "pages.json").read_text())
            self.assertEqual(len(pages["pageOrder"]), 3)
            for page in pages["pageOrder"]:
                folder = report / "definition" / "pages" / page
                metadata = json.loads((folder / "page.json").read_text())
                self.assertIn("SYNTHETIC DATA", metadata["displayName"])
                self.assertGreaterEqual(len(list((folder / "visuals").glob("*\\visual.json"))), 5)
            for file in project.rglob("*.json"):
                json.loads(file.read_text())

    def test_regeneration_is_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            build(project)
            before = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
            build(project)
            after = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
            self.assertEqual(before, after)


class VerificationTests(unittest.TestCase):
    def test_numeric_mismatch_is_rejected(self):
        expected = expected_answers(generate())
        compare("fleet", [expected["fleet"]], expected)
        incorrect = dict(expected["fleet"])
        incorrect["Total Generation MWh"] += 1
        with self.assertRaisesRegex(ValueError, "fleet"):
            compare("fleet", [incorrect], expected)

    def test_percentage_mismatch_or_missing_site_is_rejected(self):
        expected = expected_answers(generate())
        rows = [{"Site Name": site, "Capacity Factor": value}
                for site, value in expected["capacity_factor_by_site"].items()]
        compare("capacity_factor_by_site", rows, expected)
        with self.assertRaisesRegex(ValueError, "capacity_factor_by_site"):
            compare("capacity_factor_by_site", rows[:-1], expected)
        rows[0]["Capacity Factor"] += 0.001
        with self.assertRaisesRegex(ValueError, "capacity_factor_by_site"):
            compare("capacity_factor_by_site", rows, expected)


if __name__ == "__main__":
    unittest.main()
