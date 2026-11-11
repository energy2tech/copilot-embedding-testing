# Manufacturing PDF hybrid search

Five **fictional** product datasheets (pump, motor, valve, heat exchanger, sensor)
demonstrate PDF extraction and keyword, vector, and hybrid retrieval.
These are not real manufacturer specifications and must not be used operationally.

## Verified deployment

Deployed in East US to resource group `manufacturing-search-demo`:
[Search endpoint](https://srch-mfg-45b8aab5e6.search.windows.net),
index `manufacturing-products`. Authentication is required; the endpoint is
an API, not a browser UI. Five PDFs produced ten indexed chunks. All 15 live
keyword/vector/hybrid checks passed on 2026-11-11, along with three local tests.
See [deployment status](deployment-status.json) and [retrieval evidence](verification.json).
For example, "Which product monitors bearing vibration?" retrieves `SENSOR-500`,
citing [the sensor PDF](pdfs/SENSOR-500.pdf), page 1.

## Resources and costs

- One Azure AI Search **Free** service in East US (50 MB; no SLA).
  There is no automatic paid-tier fallback. Azure permits one Free service per
  subscription and may remove inactive Free services.
- One dedicated Azure OpenAI account, `text-embedding-3-small` version 1,
  Standard capacity 10, with 1,536-dimensional embeddings.
  Embeddings are pay-per-token, including query embeddings. A small demo should
  cost well under USD 1, but there is no hard budget cap.
- No Blob Storage, OCR, semantic ranking, chat model, or deployed application.
  Search stores extracted text and vectors, not the original PDF binaries.

Entra-only public HTTPS endpoints; API-key authentication is disabled.
The signed-in user receives resource-scoped Search Service Contributor,
Search Index Data Contributor, and Cognitive Services OpenAI User roles.
Provisioning requires resource creation and role-assignment permissions.

## Run (PowerShell)

```powershell
cd samples\manufacturing-search
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest -v
.\.venv\Scripts\python.exe search_demo.py generate
az login
.\provision.ps1 -SubscriptionId '<subscription-id>' -Preview
.\provision.ps1 -SubscriptionId '<subscription-id>'
.\.venv\Scripts\python.exe search_demo.py ingest
.\.venv\Scripts\python.exe search_demo.py verify
.\.venv\Scripts\python.exe search_demo.py query --mode hybrid --text 'Which product monitors bearing vibration?'
```

Preview registers required providers and creates the tagged resource group if
absent, then runs ARM validation and what-if. It does not create Search/OpenAI.
Actual provisioning uses incremental ARM deployment and writes credential-free,
git-ignored `config.local.json`. Resource names derive from subscription and
resource group. An existing untagged group is rejected.
RBAC propagation can take several minutes; if ingest reports 401/403, wait and
rerun it. Other failures must be investigated, not treated as successful ingestion.

`generate` writes five two-page PDFs under `pdfs`. `ingest` extracts actual PDF
text, chunks by page (180-word maximum with 30-word overlap), generates embeddings,
and upserts documents with stable IDs. This sample intentionally accepts only its
five named fictional products; arbitrary PDFs and scanned/OCR documents require
an ingestion extension. Source citations contain filename and 1-based page.

`verify` checks the exact indexed chunk count and rank-1 product matches for all
five products in all three retrieval modes (15 checks) and saves
`verification.json`. This tests retrieval, not generated RAG answers.
Re-ingestion updates matching chunks but does not remove obsolete chunks; use a
new index name in local configuration if changing the corpus.

## Cleanup

The script never deletes resources. When finished, review the dedicated
`manufacturing-search-demo` resource group in Azure Portal and delete it only
after confirming it contains nothing you need. This removes the Search index,
embedding deployment, account, and resource-scoped role assignments.

## References

- [Vector search quickstart](https://learn.microsoft.com/azure/search/search-get-started-vector)
- [Search RBAC](https://learn.microsoft.com/azure/search/search-security-rbac)
- [Service limits](https://learn.microsoft.com/azure/search/search-limits-quotas-capacity)
