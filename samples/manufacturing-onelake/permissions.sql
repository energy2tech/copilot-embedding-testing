-- Replace <fabric-connection-application-id> with the Databricks principal's application ID.
-- Run blocks separately in Databricks; do not execute the entire file as one batch.
-- First inspect effective catalog/schema/table grants and group memberships.
-- Do not use a connection principal with inherited SELECT on withheld tables.

-- INITIAL ENABLE: withhold quality inspections.
GRANT USE CATALOG ON CATALOG contoso_mfg_onelake_demo TO `<fabric-connection-application-id>`;
GRANT USE SCHEMA ON SCHEMA contoso_mfg_onelake_demo.manufacturing TO `<fabric-connection-application-id>`;
GRANT EXTERNAL USE SCHEMA ON SCHEMA contoso_mfg_onelake_demo.manufacturing TO `<fabric-connection-application-id>`;
GRANT SELECT ON TABLE contoso_mfg_onelake_demo.manufacturing.dim_plant TO `<fabric-connection-application-id>`;
GRANT SELECT ON TABLE contoso_mfg_onelake_demo.manufacturing.dim_machine TO `<fabric-connection-application-id>`;
GRANT SELECT ON TABLE contoso_mfg_onelake_demo.manufacturing.dim_product TO `<fabric-connection-application-id>`;
GRANT SELECT ON TABLE contoso_mfg_onelake_demo.manufacturing.dim_date TO `<fabric-connection-application-id>`;
GRANT SELECT ON TABLE contoso_mfg_onelake_demo.manufacturing.fact_work_order TO `<fabric-connection-application-id>`;
GRANT SELECT ON TABLE contoso_mfg_onelake_demo.manufacturing.fact_production TO `<fabric-connection-application-id>`;
GRANT SELECT ON TABLE contoso_mfg_onelake_demo.manufacturing.fact_downtime TO `<fabric-connection-application-id>`;

-- ENABLE QUALITY: execute after recording the withheld-table result.
GRANT SELECT ON TABLE contoso_mfg_onelake_demo.manufacturing.fact_quality_inspection TO `<fabric-connection-application-id>`;

-- DISABLE QUALITY: execute after recording successful reads; existing credentials may remain valid.
REVOKE SELECT ON TABLE contoso_mfg_onelake_demo.manufacturing.fact_quality_inspection FROM `<fabric-connection-application-id>`;

-- RESTORE QUALITY: execute after completing the revocation test.
GRANT SELECT ON TABLE contoso_mfg_onelake_demo.manufacturing.fact_quality_inspection TO `<fabric-connection-application-id>`;
