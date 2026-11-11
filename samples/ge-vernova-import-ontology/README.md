# GE Vernova-style Import model and ontology experiment

**Synthetic demonstration only.** Fictional sites, turbines, generation, and costs are not GE Vernova operational data, product specifications, or recommendations.

The experiment tests this exact chain:

**Power BI Import semantic model → new-experience Fabric ontology → Fabric data agent → DAX against that model.**

Generated ontology definitions alone are not proof of data grounding. Direct Lake, lakehouse bindings, and directly attaching a model without ontology are not substitutes.

## Current deployed state

The workspace, semantic model, and report have been created. All five **service-side** table definitions have Import partitions, full refresh completed, and all six direct-model DAX checks match the Python fixtures. See [model verification](./model-verification.json) and [deployment status](./deployment-status.json).

- [Demo workspace](https://app.powerbi.com/groups/aeeddd08-ac34-4681-b9cd-c84424c97f3e/list?ctid=21ddafdf-7740-4439-9b4a-6246817b2dfc)
- [Published report](https://app.powerbi.com/groups/aeeddd08-ac34-4681-b9cd-c84424c97f3e/reports/dd3b251a-2e5e-4c71-8524-6c401550ef97?ctid=21ddafdf-7740-4439-9b4a-6246817b2dfc)
- [Import semantic model](https://app.powerbi.com/groups/aeeddd08-ac34-4681-b9cd-c84424c97f3e/datasets/706c0186-18e0-4e89-aec6-e374518c6049/details?ctid=21ddafdf-7740-4439-9b4a-6246817b2dfc)
- [GE_Vernova_Fleet_Ontology](https://app.powerbi.com/groups/aeeddd08-ac34-4681-b9cd-c84424c97f3e/ontologies/b1c05201-f4d8-4df2-900d-f3993c86c912?ctid=21ddafdf-7740-4439-9b4a-6246817b2dfc)
- [GE Vernova Fleet Advisor](https://app.powerbi.com/groups/aeeddd08-ac34-4681-b9cd-c84424c97f3e/aiskills/664cedb7-472e-485c-a77b-70b47a18f878?ctid=21ddafdf-7740-4439-9b4a-6246817b2dfc)

The new-experience ontology was generated from the existing Import model after the user enabled ontology in tenant settings. Its exported definition references all five model tables, five relationships, and six external measures. Populated Turbine instances were observed. All five original model partitions were rechecked and remain **Import**.

The data agent was created using **Add an ontology**, automatically attaching the existing model under **Ontology data sources**. All five ontology entities are selected. Its draft and published versions returned **4,278,237 MWh** for January-March 2026, matching the independent fixture. All five published-agent acceptance cases matched the fixtures. Execution details exposed DAX and actual output against the existing semantic model. Both draft and published ontology references and synthetic-demo instructions are present in [the exported agent definition](./data-agent-definition.json).

The controlled live test increased one turbine-day by **10 MWh**. After Import refresh, the published agent returned **4,278,247 MWh** with a fresh DAX execution. The original source definition was then restored and refreshed; both the model and published agent returned the baseline generation and other fleet measures. All five source partitions still use **Import**, and the workspace retains its original F64 assignment.

All three report pages rendered, with representative site/month slicers checked and reset to defaults. One January-by-site request in a five-question batch initially returned **no answer**; asking it alone with explicit dates succeeded for all six sites. Ask one question at a time. Transient network interruptions also occurred during verification; subsequent direct-model checks passed.

This demonstrates the Import-model/ontology/published-agent path in this tenant, not a general support or production-readiness guarantee. Explicit ontology entity keys were not configured by this workflow; exploratory prompts and exhaustive report interactions were not acceptance-tested.

See [the ontology export](./ontology-definition.json), [downloaded ontology context with sample questions](../../GE_Vernova_Fleet_Ontology.md), [source-mode verification](./ontology-binding-verification.json), and [agent verification](./agent-verification.json), including the controlled change and restoration evidence.

### Generation details

Fabric's ontology name validator permits only letters, numbers, and underscores, so the actual name is **GE_Vernova_Fleet_Ontology**. Generation used the supported semantic-model **Generate Ontology** UI, not a public API creation fallback.

The ontology has internal **DirectQuery-to-Analysis-Services** entity partitions and `EXTERNALMEASURE` references to the original model. These are ontology-side connections; they do **not** change the source semantic model's Import storage mode. Fabric also automatically provisioned supporting Eventhouse, KQL Database, and GraphModel items with ontology-derived names. They were not manually substituted for the semantic-model source; preserve these managed dependencies.

The target capacity was resumed with permission and is left **running and billable** for the demo. The assistant did not modify tenant settings.

## Local project

For the separate Microsoft Foundry prompt-agent integration, provisioning scripts, authentication requirements, and end-to-end checks, see [Foundry integration](./foundry/README.md). Its verification is separate from the historical Fabric-only evidence below.

From this directory:

```powershell
python .\build_demo.py
python -m unittest -v test_demo
```

For full JSON-schema validation, install the optional validation dependencies and run:

```powershell
python -m pip install -r .\requirements-validation.txt
python .\validate_project.py
```

Open [the generated PBIP](./project/GE%20Vernova%20Fleet%20Performance%20%28Import%29.pbip) in Power BI Desktop with Power BI Project support. Refresh the model before viewing the report. PBIP contains model/report definitions, not a local imported-data cache. A PBIX can optionally be saved through Desktop.

All five tables use explicitly Import-mode, deterministic, self-contained Power Query partitions. There is no gateway, CSV path, lakehouse, or database dependency.

| Table | Grain | Rows |
|---|---|---|
| Site | Fictional site | 6 |
| Turbine | Fictional turbine | 24 |
| Date | Day, January 1–March 31, 2026 | 90 |
| Daily Generation | Turbine-day | 2,160 |
| Maintenance Event | Event | 72 |

Site filters Turbine, which filters both facts; Date filters both facts. This intentionally preserves Site and Turbine as separate ontology entities. Relationships are single-direction many-to-one with unique dimension keys. Daily rows are ordinary facts, not ontology time-series bindings.

Measures include generation MWh, downtime hours, capacity factor, maintenance cost USD, event count, and turbine count. Capacity factor is generation divided by rated MW × 24 hours for every turbine-day in the current generation-fact scope, including downtime. Maintenance costs include open and completed events and use event dates. Turbine Count is fleet inventory in site/turbine scope, not an active-turbine count filtered by fact dates.

[Expected answers](./expected-answers.json) are calculated independently in Python, not by executing the model's DAX.

To rerun the six live direct-model checks using your signed-in Azure CLI identity:

```powershell
python .\verify_model.py --workspace aeeddd08-ac34-4681-b9cd-c84424c97f3e --model 706c0186-18e0-4e89-aec6-e374518c6049
```

The verifier acquires a token in memory and writes only synthetic results and queries. A passing result validates the semantic model alone; separate browser execution evidence validates the ontology/data-agent chain.

## Deployment and artifact names

| Artifact | Name |
|---|---|
| Workspace | GE Vernova - Import Ontology Demo |
| Semantic model/report | GE Vernova Fleet Performance (Import) |
| Ontology | GE_Vernova_Fleet_Ontology |
| Data agent | GE Vernova Fleet Advisor |

Target capacity: **f64centralus001**, **F64**, **Central US**. Resuming the capacity starts continuing capacity billing; leaving it running for the demo is intentional. Pause only after coordinating with other capacity users. This sample never automatically pauses or deletes shared resources.

1. Use the intended tenant identity and confirm permissions/settings before deployment.
2. Resume the capacity if paused. Create a new dedicated workspace and assign that capacity. Do not silently reuse a same-named workspace.
3. Publish the entire model and report. For Fabric REST publication, include all TMDL definition parts; replace the report's local `byPath` model binding with the published model ID.
4. Complete initial refresh/processing and verify service-side partition metadata remains Import for every table.
5. On the semantic model, use **Generate Ontology** in the **new ontology experience**. Preview/confirm the entities and keys before creating it. Verify keys, relationship bindings, metrics, and model source references; test populated ontology queries.
6. Create the data agent, then choose **Add sources → Add an ontology**. Add the named ontology and inspect its associated semantic-model source. Use preview runtime if available, but do not assume runtime selection fixes source compatibility.
7. Refresh/download ontology context. Test the draft, publish if supported, then retest as the same user. Sharing an agent does not grant model/ontology permissions.

## Known compatibility uncertainty

- [Old ontology mode matrix](https://learn.microsoft.com/fabric/iq/ontology/old-experience/concepts-generate): Import supports schema generation, but not data bindings or querying.
- [New semantic model integration](https://learn.microsoft.com/fabric/iq/ontology/how-to-generate-from-semantic-models): describes semantic-model queries but does not explicitly certify Import mode.
- [Ontology-side data-agent guide](https://learn.microsoft.com/fabric/iq/ontology/how-to-create-data-agent): warns that data agents do not work with semantic-model-bound ontologies.
- [Newer data-agent context guide](https://learn.microsoft.com/fabric/data-science/data-agent-ontology-sources): describes ontology context with semantic-model DAX, but does not explicitly resolve that warning. It also warns that some ontology context may not be used by semantic-model query generation.

Consequently this is an **experimental compatibility test**, not a pre-certified supported solution. If a stage fails, preserve its exact error and do not claim the entire chain works. Do not use legacy lakehouse ontology payloads as a shortcut.

## Sample questions for the data agent

Open [GE Vernova Fleet Advisor](https://app.powerbi.com/groups/aeeddd08-ac34-4681-b9cd-c84424c97f3e/aiskills/664cedb7-472e-485c-a77b-70b47a18f878?ctid=21ddafdf-7740-4439-9b4a-6246817b2dfc), select **Published** if the editor opens in Draft, and paste one question at a time. Use the fixed January-March 2026 dates, not "last month" or "this quarter." All answers describe synthetic data.

### Start here: grounding demonstration

> Using GE_Vernova_Fleet_Ontology and its connected GE Vernova Fleet Performance (Import) semantic model, what is the exact total generation in MWh for January 1 through March 31, 2026? Use the model's Total Generation MWh measure, execute a query, and identify the source used.

**Expected:** **4,278,237 MWh**. This check passed in both draft and published versions. Expand **steps completed**, open the semantic-model analysis step, and select **Show input** to inspect the generated DAX and actual output. The ontology is also shown as the response source. This UI evidence is stronger than asking the agent to assert that it is grounded.

### Core demo and acceptance questions

| Copy-ready question | Expected baseline result |
|---|---|
| Show generation MWh by site for January 2026, using the existing measure. | Coastal Horizon: 246,279; Desert Vista: 247,493; Highland Point: 244,060; Lakeside: 244,998; Prairie Ridge: 244,996; Riverbend: 245,724 MWh. |
| Which five turbines had the most downtime hours in January 2026? Break ties by turbine name ascending. | Turbines 05, 11, 17, and 23: 80 hours each; Turbine 04: 79 hours. |
| Show maintenance cost in USD and maintenance event count by site from January 1 through March 31, 2026, including both open and completed events. | 12 events per site; fleet totals: 72 events and USD 369,036. Per-site costs are in the fixtures. |
| Show capacity factor by site for January 1 through March 31, 2026. Use the model's Capacity Factor % measure and display six decimal places in percentage units. | Coastal Horizon: 60.111869%; Desert Vista: 60.145960%; Highland Point: 59.960606%; Lakeside: 59.936869%; Prairie Ridge: 60.017424%; Riverbend: 59.948232%. |

All five core checks, including the grounding question above, produced matching results through the **published** agent. January generation by site required a standalone retry after an initial empty batch response. Compare responses with [the full expected answers](./expected-answers.json) and [observed agent results](./agent-verification.json).

If January generation by site produces no answer, use the more explicit tested prompt:

> Using the connected semantic model, compute Total Generation MWh by Site Name for January 1 through January 31, 2026 inclusive. Use the existing measure and return all six sites.

### Additional conversational questions

- How many turbines are in the synthetic fleet? List the sites and turbine inventory by site.
- Compare January, February, and March 2026 generation by site. Show a table and identify the largest month-to-month change.
- For January through March 2026, which site has the highest capacity factor and which has the lowest? Use the existing capacity-factor measure, not an average of percentages.
- For January through March 2026, compare maintenance cost and downtime by site. Describe the observed pattern without claiming that one causes the other.
- For Turbine 01, show January 2026 generation and downtime, then list its maintenance events during the same month.
- What reporting dates, units, and source did you use for that answer? Show the exact figures rather than rounded millions.

These additional prompts are exploratory and have not been independently acceptance-tested. Do not interpret generated summaries as operational recommendations.

### Verification checklist

Record ontology context, selected source/model ID, generated DAX, actual results, expected results, and errors. Integer values must match exactly; percentages must match at displayed precision. Validate report rendering separately.

### Controlled data-change test

```powershell
python .\build_demo.py --generation-adjustment-mwh 10
```

This changes only turbine 1 on January 1 by +10 MWh and regenerates local fixtures. For future reruns, preserve the baseline definition first, update the existing model without omitting unrelated parts, refresh its Import data, and ask the published agent to execute a fresh query. Restore adjustment 0 and refresh before handing off the demo.

**Observed live result:** **4,278,237 → 4,278,247 → 4,278,237 MWh**. The test edited only the existing live model's generation adjustment, leaving local baseline fixtures unchanged. No ontology regeneration or agent republishing was needed. The final model and agent also returned 5,400 downtime hours, USD 369,036 maintenance cost, 72 events, and 24 turbines. The source mode and capacity assignment were rechecked after restoration. See [the recorded evidence](./agent-verification.json).

Do not count pending manual UI steps, unloaded Import partitions, empty ontology instances, or a successful report upload as proof of the complete chain.
