# Reference files from the deployed (GCP) version

These are pulled as-is from the `unfi-claims-resolution-agent` GitHub repo
(the deployed Gemini Enterprise / Agent Runtime version), for use as demo
talking points and Q&A backup - not meant to be run locally. They show the
"real" architecture that `local/` simplifies for reproducibility.

Pair each with the matching table row in `local/README.md`'s
"What changed vs. the deployed version" section.

## claims_agent/ (deployed ADK agent package)

- **agent.py** - the root ADK `Agent` definition. Shows the `VertexAiSearchTool`
  + `AgentTool` workaround: Gemini won't let you mix a search/retrieval tool
  with custom function tools in the same agent, so the policy lookup lives on
  its own single-tool sub-agent (`policy_lookup_agent`), wrapped as a plain
  callable tool (`AgentTool`) for the root agent. This is the piece
  `local/agent.py` sidesteps entirely - since nothing in `local/` uses
  Gemini's server-side search tool, there's no restriction to route around,
  so all four tools sit in one flat list.
- **tools.py** - `three_way_match`, implemented against BigQuery
  (parameterized SQL joins across `deduction_claims`, `invoices`,
  `purchase_orders`, `receiving`). Compare to `local/tools.py` to see exactly
  what changed (client, query syntax) vs. what didn't (join logic, match
  rules, docstrings).
- **resolution_tool.py** - `propose_resolution`, the tool that runs the
  three-way match, drafts a recommendation, and logs a PENDING draft. Same
  recommendation text and rules as `local/tools.py`'s version - good file to
  point to if asked "does the agent ever auto-approve a deduction?" (answer:
  no, it always returns `status: pending_human_approval`).
- **case_memory_tools.py** - `log_resolution` / `get_case_history` against
  Cloud SQL (Postgres) via the Cloud SQL Python Connector. Shows the
  audit-log pattern (`case_history` table, `analyst_decision` defaults to
  `'pending'`) that `local/db.py` reproduces in SQLite.

## Deployment / infra

- **deploy.py** - deploys the ADK agent to Vertex AI **Agent Engine**
  (`vertexai.agent_engines.AdkApp`), wiring in Cloud SQL connection env vars
  and the extra pip packages the deployed runtime needs
  (`google-adk`, `google-cloud-bigquery`, `google-cloud-discoveryengine`,
  `cloud-sql-python-connector`, etc).
- **test_deployed_agent.py** - smoke-tests the live Agent Engine endpoint
  with the same three planted demo queries used locally
  (CLAIM-DEMO-001/002/003 + a deduction code lookup), via
  `async_stream_query`. Good evidence that the deployed and local versions
  give the same answers.

## data_setup/ (GCP schema provisioning)

- **create_bigquery_tables.py** - creates the `unfi_deductions` BigQuery
  dataset and all 7 tables (`suppliers`, `purchase_orders`, `shipments`,
  `receiving`, `invoices`, `deduction_codes`, `deduction_claims`), with
  month-based time partitioning on the large fact tables. Table/column
  comments map each table back to its EDI transaction type (850 = PO,
  856 = ASN/shipment, 810 = invoice, 812 = deduction claim) - useful if
  asked why the schema is shaped the way it is.
- **create_case_history_table.py** - creates the Cloud SQL Postgres
  `case_history` audit table.
- **setup_cloud_sql.sh** - provisions the Cloud SQL instance itself
  (gcloud CLI commands).

## Not included here

No top-level README, requirements file, or the Vertex AI Search policy
HTML document exist in the GitHub repo as of this pull - only the Python
package and setup scripts. If you need the actual "Supplier Deduction Key"
HTML doc that `VertexAiSearchTool` was grounded on for the demo, it isn't
in the repo and would need to be pulled from wherever it was originally
uploaded (Cloud Storage / the Vertex AI Search data store console).
