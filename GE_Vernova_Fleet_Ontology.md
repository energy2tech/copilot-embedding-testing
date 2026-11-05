# GE_Vernova_Fleet_Ontology

## ontology.md

You are a data assistant answering questions over the
"GE_Vernova_Fleet_Ontology" data domain.  You have the following
datasource(s):

* `GE Vernova Fleet Performance (Import)` (semantic model, DAX) -- model tables and columns queried through the semantic model.

The text below is a compact view of the ontology, **merged with
the physical bindings** that map semantic names to the actual
table and column names in those datasources.  Use it as a
reference when the schemas alone are not enough.

How to read this document
-------------------------

Datasources use heavily abbreviated column names (`al_id`,
`pax_id`, `loya_tier`, ...).  This document tells you what the
ontology calls each one.

For each entity:

    EntityName  (table=<table>, id=<id_prop>, disp=<name_prop>)
        props: Property1 = model_col1, Property2, ...

* `EntityName` is the semantic name; `<table>` is the actual
  table name.  `id=` is the natural-key property; `disp=` is the
  display-name property (when defined).
* `label:` is a human-readable label for the entity or relationship
  type. It is not an instance display-name property; keep the
  semantic identity when referring to tools.
* When present, `note:` describes an element, `aka:` lists the
  synonyms users may use for it (map them to this element), and
  `meta:` carries curated key=value attributes.  They appear on an
  entity (its own lines), a property (`prop <Name>: note: ... |
  aka: ... | meta: ...`), or a relationship (an indented line
  below its join spec).

* Semantic model datasources use the same ontology aliases for model
  tables and columns, then execute through the semantic model's DAX
  tool.  Do not rewrite these as SQL/KQL physical table names.

Rules of thumb
--------------

* **Use a semantic model datasource** when the question is about
  the model tables and columns listed by the ontology and should be
  answered through DAX.

* Prefer the ontology vocabulary when explaining results (e.g.
  say "passenger" rather than "pax").
* If a user concept is not in this document, fall back to the raw
  schemas and do not invent fields.

--- BEGIN ONTOLOGY ---
Ontology: GE_Vernova_Fleet_Ontology

== ENTITIES ==

Daily Generation  (table=Daily Generation)
  note: Synthetic demo only. 2160 rows; see README for grain and metric definitions.
  props: DateKey=DateKey, Downtime Hours Raw=Downtime Hours, Generation MWh=Generation MWh, GenerationId=GenerationId, TurbineId=TurbineId

Date  (table=Date)
  note: Synthetic demo only. 90 rows; see README for grain and metric definitions.
  props: Date, DateKey=DateKey, Month, Month Number=Month Number, Year

Maintenance Event  (table=Maintenance Event)
  note: Synthetic demo only. 72 rows; see README for grain and metric definitions.
  props: Category, Cost USD, DateKey=DateKey, MaintenanceEventId=MaintenanceEventId, Status, TurbineId=TurbineId

Site  (table=Site)
  note: Synthetic demo only. 6 rows; see README for grain and metric definitions.
  props: Region, Site Name=Site Name, SiteId=SiteId

Turbine  (table=Turbine)
  note: Synthetic demo only. 24 rows; see README for grain and metric definitions.
  props: Rated MW, SiteId=SiteId, Technology, Turbine Name=Turbine Name, TurbineId=TurbineId
--- END ONTOLOGY ---

## ge-vernova-fleet-performance-import.md

This datasource is a semantic model (DAX). It holds the model tables
and columns selected by the ontology and should be queried through
the semantic model tool.

The block below is the slice of the ontology bound to this semantic
model: entity -> model table mapping and non-obvious column aliases.
Properties listed bare (no ``= model_col``) use a column whose name
is the snake_case form of the property name.

Hard constraints on this datasource:

* Query it with DAX through the semantic model tool.
* Do not invent SQL/KQL tables or cross-datasource joins inside this
  semantic model query.

--- BEGIN SEMANTIC MODEL ONTOLOGY SLICE ---
Ontology: GE_Vernova_Fleet_Ontology

== ENTITIES ==

Daily Generation  (table=Daily Generation)
  note: Synthetic demo only. 2160 rows; see README for grain and metric definitions.
  props: DateKey=DateKey, Downtime Hours Raw=Downtime Hours, Generation MWh=Generation MWh, GenerationId=GenerationId, TurbineId=TurbineId

Date  (table=Date)
  note: Synthetic demo only. 90 rows; see README for grain and metric definitions.
  props: Date, DateKey=DateKey, Month, Month Number=Month Number, Year

Maintenance Event  (table=Maintenance Event)
  note: Synthetic demo only. 72 rows; see README for grain and metric definitions.
  props: Category, Cost USD, DateKey=DateKey, MaintenanceEventId=MaintenanceEventId, Status, TurbineId=TurbineId

Site  (table=Site)
  note: Synthetic demo only. 6 rows; see README for grain and metric definitions.
  props: Region, Site Name=Site Name, SiteId=SiteId

Turbine  (table=Turbine)
  note: Synthetic demo only. 24 rows; see README for grain and metric definitions.
  props: Rated MW, SiteId=SiteId, Technology, Turbine Name=Turbine Name, TurbineId=TurbineId
--- END SEMANTIC MODEL ONTOLOGY SLICE ---

## Sample questions for GE Vernova Fleet Advisor

These are synthetic demo questions, separate from the generated ontology context above. Open [GE Vernova Fleet Advisor](https://app.powerbi.com/groups/aeeddd08-ac34-4681-b9cd-c84424c97f3e/aiskills/664cedb7-472e-485c-a77b-70b47a18f878?ctid=21ddafdf-7740-4439-9b4a-6246817b2dfc), select **Published**, and ask one question at a time.

1. **Using GE_Vernova_Fleet_Ontology and its connected Import semantic model, what is the exact total generation in MWh for January 1 through March 31, 2026? Execute a query using the existing measure and identify the source.**
   Expected: **4,278,237 MWh**.
2. **Show Total Generation MWh by Site Name for January 1 through January 31, 2026 inclusive. Use the existing measure and return all six sites.**
   Expected: Coastal Horizon **246,279**; Desert Vista **247,493**; Highland Point **244,060**; Lakeside **244,998**; Prairie Ridge **244,996**; Riverbend **245,724 MWh**.
3. **Which five turbines had the most downtime hours in January 2026? Break ties by turbine name ascending.**
   Expected: Turbines **05, 11, 17, 23: 80 hours** each; Turbine **04: 79 hours**.
4. **Show maintenance cost in USD and maintenance event count by site for January 1 through March 31, 2026, including open and completed events.**
   Expected: **12 events per site**, **72 total**, and **USD 369,036** total cost.
5. **Show capacity factor by site for January 1 through March 31, 2026. Use the existing Capacity Factor % measure and display six decimal places in percentage units.**
   Expected: Coastal Horizon **60.111869%**; Desert Vista **60.145960%**; Highland Point **59.960606%**; Lakeside **59.936869%**; Prairie Ridge **60.017424%**; Riverbend **59.948232%**.

All five checks matched the published agent's responses; the January-by-site check required a standalone retry after an empty batch response. Expand **steps completed**, open the semantic-model analysis step, and select **Show input** to inspect DAX and actual output.

See the [demo README](samples/ge-vernova-import-ontology/README.md#sample-questions-for-the-data-agent) for additional exploratory questions, metric definitions, verification evidence, and preview limitations. The controlled refresh test produced **4,278,237 -> 4,278,247 -> 4,278,237 MWh**, and the baseline has been restored.
