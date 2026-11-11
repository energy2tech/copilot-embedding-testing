"""Generate fictional PDFs, index their extracted text, and test hybrid retrieval."""

import argparse
import hashlib
import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path

from azure.identity import AzureCliCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SearchableField,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from azure.search.documents.models import VectorizedQuery
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).resolve().parent
DIMENSIONS = 1536
PRODUCTS = [
    {
        "id": "PUMP-100", "name": "ClearFlow centrifugal pump",
        "category": "Pump",
        "description": "Transfers clean process water in manufacturing cooling loops.",
        "specs": "Illustrative flow 120 litres per minute; head 35 metres; 316 stainless steel wetted parts; 3 kW motor.",
        "application": "Cooling-water circulation and clean-water transfer. Not specified for abrasive slurry or hazardous fluids.",
    },
    {
        "id": "MOTOR-200", "name": "TorqueLine induction motor",
        "category": "Motor",
        "description": "Three-phase electric drive for conveyors and industrial machinery.",
        "specs": "Illustrative output 7.5 kW; supply 400 V; nominal speed 1470 rpm; IP55 enclosure; IE3 efficiency class.",
        "application": "Fixed-speed conveyor drives and general factory equipment. Drive compatibility requires engineering review.",
    },
    {
        "id": "VALVE-300", "name": "SealPoint control valve",
        "category": "Valve",
        "description": "Modulates process-water flow using a pneumatic actuator.",
        "specs": "Illustrative DN50 globe valve; stainless steel body; 4-20 mA positioner; PN16 pressure class.",
        "application": "Automated water-flow regulation in production skids. Not a certified safety isolation device.",
    },
    {
        "id": "HX-400", "name": "ThermaPlate heat exchanger",
        "category": "Heat exchanger",
        "description": "Transfers heat between two separated water circuits using gasketed plates.",
        "specs": "Illustrative duty 150 kW; 316 stainless steel plates; EPDM gaskets; 10 bar design pressure.",
        "application": "Separates a process cooling loop from a utility water loop. Actual sizing requires thermal engineering.",
    },
    {
        "id": "SENSOR-500", "name": "VibeWatch vibration sensor",
        "category": "Sensor",
        "description": "Monitors machine bearing vibration for condition monitoring and predictive maintenance.",
        "specs": "Illustrative measurement range 0-25 mm/s RMS; 10-1000 Hz band; IO-Link interface; IP67 enclosure.",
        "application": "Bearing-condition trend monitoring on pumps and motors. Not a protective shutdown instrument.",
    },
]


def generate_pdfs(folder: Path) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for product in PRODUCTS:
        path = folder / f"{product['id']}.pdf"
        canvas = Canvas(str(path), pagesize=A4, invariant=1)
        canvas.setTitle(f"{product['id']} {product['name']} - fictional sample")
        for heading, paragraphs in [
            ("Product overview", [product["description"], product["specs"]]),
            ("Applications and limitations", [product["application"],
             "This is invented demo data, not a real manufacturer datasheet.",
             "Do not use these specifications for selection, installation, or operation."]),
        ]:
            text = canvas.beginText(45, 790)
            text.setFont("Helvetica", 11)
            import textwrap

            for line in [
                "FICTIONAL MANUFACTURING PRODUCT - DEMO ONLY",
                f"{product['id']} | {product['name']}",
                f"Category: {product['category']}", heading, "",
            ]:
                text.textLine(line)
            for paragraph in paragraphs:
                for line in textwrap.wrap(paragraph, width=88):
                    text.textLine(line)
                text.textLine("")
            canvas.drawText(text)
            canvas.showPage()
        canvas.save()
        paths.append(path)
    return paths


def chunk_text(text: str, size: int = 180, overlap: int = 30) -> list[str]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Require size > 0 and 0 <= overlap < size.")
    words = text.split()
    chunks = []
    for start in range(0, len(words), size - overlap):
        chunks.append(" ".join(words[start:start + size]))
        if start + size >= len(words):
            break
    return chunks


def extract_documents(folder: Path) -> list[dict]:
    paths = sorted(folder.glob("*.pdf"))
    if not paths:
        raise ValueError(f"No PDF files in {folder}")
    products = {p["id"]: p for p in PRODUCTS}
    documents = []
    for path in paths:
        product = products.get(path.stem)
        if product is None:
            raise ValueError(f"Unknown sample product: {path.name}")
        for page_number, page in enumerate(PdfReader(path).pages, 1):
            text = page.extract_text()
            if not text or not text.strip():
                raise ValueError(f"No extractable text: {path.name}, page {page_number}. OCR is not configured.")
            for chunk_number, chunk in enumerate(chunk_text(text)):
                key = f"{path.name}:{page_number}:{chunk_number}"
                documents.append({
                    "id": hashlib.sha256(key.encode()).hexdigest(),
                    "product_id": product["id"], "title": product["name"],
                    "category": product["category"], "source_file": path.name,
                    "page": page_number, "content": chunk,
                })
    return documents


def make_index(name: str) -> SearchIndex:
    return SearchIndex(
        name=name,
        fields=[
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SimpleField(name="product_id", type=SearchFieldDataType.String, filterable=True),
            SearchableField(name="title"),
            SimpleField(name="category", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="source_file", type=SearchFieldDataType.String),
            SimpleField(name="page", type=SearchFieldDataType.Int32),
            SearchableField(name="content"),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True, hidden=True,
                vector_search_dimensions=DIMENSIONS,
                vector_search_profile_name="products-vector",
            ),
        ],
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="products-hnsw")],
            profiles=[VectorSearchProfile(
                name="products-vector", algorithm_configuration_name="products-hnsw",
            )],
        ),
    )


def embed(texts: list[str], config: dict, credential: AzureCliCredential) -> list[list[float]]:
    token = credential.get_token("https://cognitiveservices.azure.com/.default").token
    url = (f"{config['openaiEndpoint'].rstrip('/')}/openai/deployments/"
           f"{config['embeddingDeployment']}/embeddings?api-version=2024-02-01")
    request = urllib.request.Request(
        url, data=json.dumps({"input": texts, "dimensions": DIMENSIONS}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.load(response)
            break
        except urllib.error.HTTPError as error:
            detail = error.read().decode()
            if error.code not in (429, 503) or attempt == 5:
                raise RuntimeError(f"Embedding HTTP {error.code}: {detail}") from error
            delay = min(60, 2 ** (attempt + 1))
            print(f"Embedding HTTP {error.code}; retrying in {delay}s.")
            time.sleep(delay)
    rows = sorted(payload["data"], key=lambda row: row["index"])
    if [row["index"] for row in rows] != list(range(len(texts))):
        raise ValueError("Embedding response indices do not match inputs.")
    vectors = [row["embedding"] for row in rows]
    if any(len(v) != DIMENSIONS or not all(math.isfinite(x) for x in v) for v in vectors):
        raise ValueError("Invalid embedding dimensions or values.")
    return vectors


def query(client: SearchClient, text: str, mode: str, vector: list[float] | None = None) -> list[dict]:
    kwargs = {}
    if mode != "keyword":
        if vector is None:
            raise ValueError("Vector required for vector or hybrid search.")
        kwargs["vector_queries"] = [
            VectorizedQuery(vector=vector, k_nearest_neighbors=10, fields="content_vector")
        ]
    results = client.search(
        search_text=text if mode != "vector" else None,
        search_fields=["title", "content"], top=3,
        select=["product_id", "title", "source_file", "page", "content"], **kwargs,
    )
    return [dict(row) for row in results]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["generate", "ingest", "verify", "query"])
    parser.add_argument("--config", type=Path, default=ROOT / "config.local.json")
    parser.add_argument("--pdf-dir", type=Path, default=ROOT / "pdfs")
    parser.add_argument("--text", default="Which product monitors bearing vibration?")
    parser.add_argument("--mode", choices=["keyword", "vector", "hybrid"], default="hybrid")
    args = parser.parse_args()
    if args.command == "generate":
        paths = generate_pdfs(args.pdf_dir)
        documents = extract_documents(args.pdf_dir)
        print(f"Generated {len(paths)} PDFs; extracted {len(documents)} page chunks.")
        return
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    with AzureCliCredential(tenant_id=config["tenantId"]) as credential:
        with SearchClient(config["searchEndpoint"], config["indexName"], credential) as client:
            if args.command == "ingest":
                documents = extract_documents(args.pdf_dir)
                vectors = embed([doc["content"] for doc in documents], config, credential)
                for doc, vector in zip(documents, vectors, strict=True):
                    doc["content_vector"] = vector
                with SearchIndexClient(config["searchEndpoint"], credential) as indexes:
                    indexes.create_or_update_index(make_index(config["indexName"]))
                results = client.merge_or_upload_documents(documents)
                failures = [r for r in results if not r.succeeded]
                if failures:
                    raise RuntimeError(f"Index upload failed: {[(r.key, r.error_message) for r in failures]}")
                print(f"Uploaded {len(documents)} chunks from actual PDF extraction.")
            elif args.command == "query":
                vector = None if args.mode == "keyword" else embed([args.text], config, credential)[0]
                print(json.dumps(query(client, args.text, args.mode, vector), indent=2))
            else:
                expected_count = len(extract_documents(args.pdf_dir))
                for attempt in range(12):
                    count = client.get_document_count()
                    if count == expected_count:
                        break
                    print(f"Index visibility: {count}/{expected_count}; waiting 5s.")
                    time.sleep(5)
                if count != expected_count:
                    raise RuntimeError(f"Expected {expected_count} indexed chunks, got {count}.")
                cases = [
                    ("PUMP-100", "centrifugal pump for clean process water"),
                    ("MOTOR-200", "three phase conveyor electric motor"),
                    ("VALVE-300", "pneumatic control valve with positioner"),
                    ("HX-400", "transfer heat between separated water circuits"),
                    ("SENSOR-500", "bearing vibration condition monitoring sensor"),
                ]
                vectors = embed([text for _, text in cases], config, credential)
                checks = []
                for (expected, text), vector in zip(cases, vectors, strict=True):
                    for mode in ("keyword", "vector", "hybrid"):
                        rows = query(client, text, mode, vector)
                        if not rows or rows[0]["product_id"] != expected:
                            raise AssertionError(f"{mode}: expected {expected} at rank 1, got {rows}")
                        if not all(row["source_file"] and row["page"] >= 1 for row in rows):
                            raise AssertionError("Missing source citations.")
                        checks.append({
                            "mode": mode, "query": text, "expected": expected,
                            "top_product": rows[0]["product_id"],
                            "source_file": rows[0]["source_file"], "page": rows[0]["page"],
                        })
                evidence = {
                    "index": config["indexName"], "document_count": count,
                    "pdf_count": len(list(args.pdf_dir.glob("*.pdf"))),
                    "embedding_model": config["embeddingDeployment"],
                    "dimensions": DIMENSIONS, "checks": checks,
                    "verified_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                (ROOT / "verification.json").write_text(json.dumps(evidence, indent=2) + "\n")
                print(f"PASS: {len(checks)} live retrieval checks; {count} chunks with source metadata.")


if __name__ == "__main__":
    main()
