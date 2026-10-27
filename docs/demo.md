# DataPilot AI demo

1. Launch with `launch.ps1` and open the local URL.
2. Select **Explore reference data**, using Year 2010-2011. Explain that actual dataset counts are calculated, not examples.
3. Open Dataset Explorer; inspect raw and prepared views, schema, missingness, and previews.
4. Open Data Quality. Inspect the score formula, affected rows, aliases, cancellations, malformed values and IQR signals. Preview duplicate removal, compare the proposed result, then apply it. Switch back to raw to demonstrate preservation.
5. Return to Dashboard, filter by country or date, and inspect full-dataset aggregates. Reset filters.
6. Open Ask DataPilot and ask: **What are the top 5 countries by revenue?** Inspect the calculated-result badge, SQL and execution details. Then **Exclude the UK**, **Show only 3** and **Show that as a chart**. Reopen an earlier answer from session history.
7. Ask for customer age. The application must not manufacture unavailable attributes.
8. Generate Automatic Insights; read the executive briefing and inspect supporting tables/SQL on a finding card.
9. Analyze Customer Intelligence. Explain RFM, scaling, cluster profiles, revenue contributions and label rationale. Search a customer ID to open its profile. Ask **Which customers are at risk?** in Ask DataPilot.
10. Run Anomaly Detection. Inspect the score distribution and compare a selected transaction with the scored population. Explain that unusual transactions do not establish fraud.
11. Export the cleaned dataset or customer memberships, and show the tests and [upgrade verification report](upgrade_verification.md).
12. Open the provider status dialog. Explain local Ollama versus remote hosted configuration and the information sent to AI. If no model is available, demonstrate that exploration, calculations, quality, insights and ML still work.

For a generic-data demonstration, upload a CSV with category, date, and numeric columns. Retail-specific features should explain their prerequisites while exploration, SQL, statistics, charts, and generic insights continue to work.
