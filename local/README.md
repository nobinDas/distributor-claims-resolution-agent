# UNFI Claims Resolution Agent - local version

This is a local, terminal-chat version of the deployed capstone agent.
Same four tools, same reasoning, same three planted demo cases - but no
GCP project, BigQuery, Cloud SQL, Vertex AI Search, or Agent Runtime
required. Everything runs on your machine.

## What changed vs. the deployed version

| Deployed (Gemini Enterprise)          | Local (this folder)                          |
|----------------------------------------|-----------------------------------------------|
| Business data in BigQuery              | Same schema, in a local SQLite file (`claims.db`) |
| Audit log in Cloud SQL Postgres        | Same `case_history` table, in the same SQLite file |
| Policy lookup via `VertexAiSearchTool` (RAG over an HTML doc) | Direct lookup against the `deduction_codes` table - same source data, no vector search needed for 12 rows |
| ADK `Agent` + Agent Runtime deployment | Plain `google-genai` call to the Gemini API (AI Studio key), with automatic function calling |
| Chat via Gemini Enterprise             | Chat via `chat.py` in your terminal |

The tool logic (`three_way_match`, `propose_resolution`, `get_case_history`)
and the planted demo cases (`CLAIM-DEMO-001/002/003`) are unchanged - same
seed (42), same fixture data, same expected outcomes. Only the storage
backend and the model-calling layer changed.

## Setup

1. **Install dependencies** (from inside this `local/` folder):
   ```bash
   pip install -r requirements.txt
   ```

2. **Get a Gemini API key** (free tier, AI Studio - not Vertex, no GCP
   project needed): https://aistudio.google.com/apikey

3. **Set your key**:
   ```bash
   cp .env.example .env
   # then edit .env and paste your key in place of "your-api-key-here"
   ```

4. **Generate the local dataset** (creates `claims.db` next to this file,
   same seed/logic as the original BigQuery generator):
   ```bash
   python generate_synthetic_data.py
   ```
   Re-run this anytime to reset to a fresh dataset - it truncates and
   reloads all tables.

5. **Chat with the agent**:
   ```bash
   python chat.py
   ```

## Try these in the chat

```
Look up CLAIM-DEMO-001
What does deduction code DAMAGE-02 mean?
Propose a resolution for CLAIM-DEMO-003
Has CLAIM-DEMO-002 been looked at before?
Propose a resolution for CLAIM-DEMO-002, then check its case history
```

Expected outcomes for the three planted cases (unchanged from the deployed
version):

- **CLAIM-DEMO-001** - confirmed 20-unit shortage -> agent should recommend
  upholding the $240 deduction.
- **CLAIM-DEMO-002** - fully received, no discrepancy -> agent should
  recommend reversing the $105 deduction.
- **CLAIM-DEMO-003** - quantity matches but condition notes say "damaged"
  with no unit count -> agent should recommend escalation to a human, not
  auto-resolve.

## Files

- `db.py` - SQLite schema + connection helper (replaces BigQuery dataset +
  Cloud SQL instance).
- `generate_synthetic_data.py` - same generator as
  `data/setup/generate_synthetic_data.py` in the repo root, writing to
  SQLite instead of BigQuery.
- `tools.py` - the four agent tools, reimplemented against SQLite.
  `lookup_deduction_policy` replaces the `VertexAiSearchTool` RAG lookup
  with a direct query against the same underlying reference data.
- `agent.py` - builds a Gemini API chat session with the four tools
  registered for automatic function calling.
- `chat.py` - terminal REPL.

## Notes / things to keep in mind

- **This is a simplification of the RAG piece, not a re-implementation of
  it.** The deployed version demonstrates Vertex AI Search grounding over
  an unstructured HTML policy document - a real RAG pipeline. Locally,
  `lookup_deduction_policy` is a direct SQL lookup against the 12-row
  `deduction_codes` table, since that's genuinely a better fit at this
  scale (RAG doesn't add value for 12 short reference rows) - it's what your
  own project learnings already concluded (RAG is justified for volatile
  or large-document policy content, not small structured reference data).
  If your capstone writeup specifically needs to demonstrate embeddings-based
  retrieval locally, say so and I can add a small local vector-search
  version instead (e.g. embedding the deduction key text with the Gemini
  embeddings API and doing cosine-similarity lookup) - but it would be
  strictly more machinery for the same 12 rows.
- **Automatic function calling** (google-genai passing plain Python
  functions into `tools=[]`) replaces both ADK's tool orchestration and the
  policy-lookup sub-agent/`AgentTool` workaround from `claims_agent/agent.py`
  - that workaround existed specifically because Gemini disallows mixing
  `VertexAiSearchTool` with function tools in one agent; since nothing here
  uses Gemini's server-side search tool anymore, the restriction doesn't
  apply and everything fits in one flat tool list.
- `claims.db` is created next to these scripts and is already covered by
  the repo's existing `.gitignore` patterns for local data/credentials -
  double check before committing if you add this folder to git.
