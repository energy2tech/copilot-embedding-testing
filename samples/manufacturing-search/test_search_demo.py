import tempfile
import unittest
from pathlib import Path

from search_demo import PRODUCTS, chunk_text, extract_documents, generate_pdfs


class PdfTests(unittest.TestCase):
    def test_pdf_roundtrip_and_source_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            paths = generate_pdfs(folder)
            documents = extract_documents(folder)
            self.assertEqual(len(paths), 5)
            self.assertEqual(len(documents), 10)
            self.assertEqual(len({d["id"] for d in documents}), len(documents))
            for product in PRODUCTS:
                rows = [d for d in documents if d["product_id"] == product["id"]]
                self.assertEqual({d["page"] for d in rows}, {1, 2})
                self.assertIn(product["description"], rows[0]["content"])
                self.assertEqual(rows[0]["source_file"], f"{product['id']}.pdf")
                self.assertIn("FICTIONAL", rows[0]["content"])

    def test_chunk_overlap_and_terminal_boundary(self):
        words = [str(n) for n in range(25)]
        chunks = chunk_text(" ".join(words), size=10, overlap=3)
        self.assertEqual([len(c.split()) for c in chunks], [10, 10, 10, 4])
        self.assertEqual(chunks[0].split()[-3:], chunks[1].split()[:3])
        self.assertEqual(chunks[-1].split()[-1], "24")
        self.assertEqual(chunk_text("a b c", size=3, overlap=1), ["a b c"])
        self.assertEqual(chunk_text(""), [])
        with self.assertRaises(ValueError):
            chunk_text("text", size=3, overlap=3)

    def test_missing_pdfs_fail_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "No PDF"):
                extract_documents(Path(directory))


if __name__ == "__main__":
    unittest.main()
