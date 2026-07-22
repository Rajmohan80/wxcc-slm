# AbhavTech WxCC SLM

**A domain-specific AI consulting system for Cisco Webex Contact Center — demo build**

> **Status:** Active development · Demo build · Not yet deployed to production

[![Build Status](https://img.shields.io/github/actions/workflow/status/rajmohan80/wxcc-slm/ci.yml?style=flat-square&label=CI)](https://github.com/rajmohan80/wxcc-slm/actions)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square)](https://python.org)

---

## What this is

Most AI assistants answer general questions. This system is designed to answer **one specific question type** with verifiable, traceable reasoning:

> *"Given this customer's contact centre scenario, what is the correct Cisco Webex Contact Center architecture, and what are the compliance, capacity, and migration constraints?"*

That question requires CCIE-level reasoning across product knowledge, capacity rules, data residency regulations, migration risk, and architecture patterns. This system encodes 18 years of that reasoning — explicitly, verifiably, and traceably — into a structured knowledge layer backed by a RAG pipeline.

It is not a chatbot. It is a **domain-specific AI consulting system**.

This repository is a **demo/portfolio build** — the pipeline runs locally, the knowledge base is complete, and the architecture is production-ready. Cloud Run deployment, public Streamlit demo, and n8n automation are in the roadmap (see [Build status](#build-status)).

---

## Architecture

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────┐
│              Intent Flow Pipeline               │
│  (LangChain + LangGraph · 9-step state machine) │
│                                                 │
│  1. Intent Classifier      ← Groq/Llama-3.3-70B │
│  2. Scenario Detector      ← Groq/Llama-3.3-70B │
│  3. Requirement Checker    ← workbook rules     │
│  4. Stop Condition Check   ← hard rules         │
│  5. Missing Info?          ← ask / proceed      │
│  6. RAG Retrieval          ← Qdrant + BGE-M3    │
│  7. Compliance Flags       ← workbook rules     │
│  8. Architecture Generator ← Groq/Llama-3.3-70B │
│  9. Best-Practice Validate ← workbook rules     │
└─────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────┐
│              Knowledge Layer                    │
│                                                 │
│  Workbook A: Requirements (348 rows, 6 tabs)    │
│  Workbook B: Product Knowledge (478 rows, 11t)  │
│  Workbook C: Architecture (254 rows, 10 tabs)   │
│  Workbook D: Engineering (414 rows, 11 tabs)    │
│                                                 │
│  RAG Corpus: 48+ Cisco/GCP/Compliance docs      │
│  Vector DB:  Qdrant Cloud (BGE-M3, dim=1024)    │
│              2,633 chunks ingested              │
└─────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────┐
│         Delivery Layer (demo / local)           │
│                                                 │
│  FastAPI REST API  (localhost:8000)             │
│  MCP Server        (11 tools · FastMCP)         │
│  Streamlit UI      (localhost:8501)             │
│                                                 │
│  Planned: Cloud Run · abhavtech.com · n8n       │
└─────────────────────────────────────────────────┘
```

---

## Build status

| Component | Status | Notes |
|---|---|---|
| Workbooks A–D (1,414 rows) | ✅ Complete | Core knowledge layer |
| Corpus tooling (4 scripts) | ✅ Complete | Download → verify → ingest pipeline |
| Qdrant corpus (2,633 chunks) | ✅ Ingested | BGE-M3, 48 docs, 14 folders |
| RAG pipeline (`query_engine.py`) | ✅ Complete | Provenance-ranked retrieval |
| Intent flow (`slm_pipeline.py`) | ✅ Complete | 9-step LangGraph state machine |
| LangChain agent (`slm_agent.py`) | ✅ Complete | ReAct agent with tool calling |
| Session memory (LangGraph) | ✅ Complete | `MemorySaver` + thread isolation |
| FastAPI REST (`api_server.py`) | ✅ Complete | Runs locally on port 8000 |
| MCP server (11 tools) | ✅ Complete | FastMCP, runs locally |
| Streamlit UI | ✅ Complete | Runs locally on port 8501 |
| Cloud Run deployment | ⏳ Planned | Post-demo validation |
| Public Streamlit demo | ⏳ Planned | Pending Cloud Run |
| n8n automation (Phase 7) | ⏳ In pipeline | Spec complete — see `docs/phase7_n8n_spec.md` |
| MkDocs site | ⏳ Planned | 44 pages designed, not deployed |
| Golden test validation (49 Qs) | ⏳ In progress | Pipeline + MCP integration phase |

---

## Why this architecture

### The intelligence is in the workbooks, not the model

Enterprise AI consulting fails when intelligence lives only in model weights. Weights are opaque, unauditable, and stale the moment a new Cisco release ships.

This system puts the intelligence where it belongs:

| Layer | What it contains | Why it matters |
|---|---|---|
| **Workbook A** | 104-question discovery checklist, ask/assume/stop rules, 15 scenario domains | Every requirement field the SLM must collect before generating any design |
| **Workbook B** | Full product capability matrix, WxCC vs Avaya/Genesys/Amazon/Five9 feature parity, data locality across 8 DCs | The product knowledge the model retrieves, not invents |
| **Workbook C** | 18 reference architectures, 7 migration playbooks, HA/DR/security/compliance patterns | Architecture choices are pattern-matched, not hallucinated |
| **Workbook D** | Capacity calculators, 32 pre-populated risks, 36-item validation checklist, 8 troubleshooting trees | Engineering guardrails applied after generation |

The model classifies, retrieves, and formats. The workbooks decide what is correct.

### Provenance is a hard requirement

Every corpus document carries a provenance tier:

- **Tier 1** — Official Cisco/GCP/regulator primary source. Ranked higher at retrieval.
- **Tier 2** — AbhavTech-authored synthesis. Never ranked above Tier 1 on the same topic.

Every generated response carries a `knowledge-current-as-of` stamp. The planned n8n automation loop (Phase 7) will keep that stamp honest by checking sources weekly and flagging stale content.

### Stop conditions before design

Some queries must never reach the design generator. For example:

```
Query: "Design a WxCC deployment for mainland China"
→ STOP. Hard blocker. Mainland China is not in Cisco's data locality tables.
   Alternative: Hong Kong → Singapore DC (SG1). Latency and cross-border analysis apply.
   (Source: Cisco n0p6xa1, 27 May 2026)
```

The stop-condition check runs before any LLM call on the generation step.

---

## Repository structure

```
wxcc-slm/
│
├── corpus_tools/              # Corpus management (download → verify → ingest)
│   ├── corpus_manifest.json   # Source of truth: 52 entries, 14 folders
│   ├── 1_create_folders.py    # Scaffold 14-folder taxonomy
│   ├── 2_download_corpus.py   # Fetch, strip boilerplate, stamp provenance
│   ├── 3_verify_corpus.py     # Pre-ingest checks (dedup, provenance, boilerplate)
│   └── 4_ingest_corpus.py     # Qdrant upsert with active/supersedes versioning
│
├── pipeline/                  # RAG + intent flow
│   ├── slm_pipeline.py        # 9-step intent flow orchestration
│   ├── query_engine.py        # Qdrant retrieval + provenance-ranked scoring
│   └── prompt_builder.py      # System prompt + classification prompt assembly
│
├── api/                       # REST API (local dev)
│   └── api_server.py          # FastAPI: /query, /health
│
├── mcp_server/                # MCP server (11 tools, local dev)
│   ├── tools/                 # Individual tool implementations
│   └── n8n_workflows/         # Phase 7 workflow exports (pending)
│
├── knowledge/                 # Structured knowledge base
│   └── README.md              # Schema reference (workbooks not committed — proprietary)
│
├── notebooks/                 # Validation and exploration
│
├── docs/
│   ├── architecture.md        # Full system design + stack decisions
│   ├── phase7_n8n_spec.md     # 4-workflow n8n automation spec (in pipeline)
│   ├── knowledge_schema.md    # Workbooks A–D schema reference
│   └── gap_register.md        # Known gaps and open VERIFY flags
│
├── .github/workflows/ci.yml   # Smoke test on push
└── .env.example               # Required env vars
```

---

## Tech stack

| Component | Technology | Status |
|---|---|---|
| **LLM (current)** | Groq Llama-3.3-70B | ✅ Running |
| **LLM (planned)** | Claude Haiku 4.5 (classify) + Sonnet 4.6 (generate) | ⏳ Anthropic billing pending |
| **Embedding** | BGE-M3 (BAAI, 1024-dim, cached locally) | ✅ Ingested |
| **Vector DB** | Qdrant Cloud (free tier, 2,633 chunks) | ✅ Running |
| **Orchestration** | LangChain + LangGraph | ✅ Running |
| **MCP Server** | FastMCP (11 tools) | ✅ Running locally |
| **REST API** | FastAPI (localhost:8000) | ✅ Running locally |
| **Automation** | n8n (4 workflows) | ⏳ Spec complete, not yet running |
| **Frontend** | Streamlit (localhost:8501) | ✅ Running locally |
| **Deployment** | GCP Cloud Run | ⏳ Planned |
| **Observability** | MLflow + Evidently AI | ⏳ Planned |

**V2 (enterprise/sovereign):** Qwen3 8B Instruct, self-hosted via Ollama on customer infrastructure. Triggered by enterprise demand, not a build schedule. Same pipeline — one endpoint swap.

---

## Running locally

```bash
git clone https://github.com/rajmohan80/wxcc-slm.git
cd wxcc-slm
pip install -r requirements.txt
cp .env.example .env          # fill in GROQ_API_KEY and QDRANT_URL / QDRANT_KEY
```

**Corpus setup (first time):**

```bash
cd corpus_tools
python 1_create_folders.py --corpus-dir ./webex_slm_corpus
python 2_download_corpus.py --corpus-dir ./webex_slm_corpus --batch 2
python 3_verify_corpus.py   --corpus-dir ./webex_slm_corpus
python 4_ingest_corpus.py   --corpus-dir ./webex_slm_corpus \
    --qdrant-url $QDRANT_URL --qdrant-key $QDRANT_KEY
```

**Start the API:**

```bash
uvicorn api.api_server:app --host 0.0.0.0 --port 8000 --reload
```

**Query the pipeline directly:**

```bash
python -m pipeline.slm_pipeline "Where does a UAE customer's WxCC data reside?"
```

---

## Example queries

| Query | What the pipeline does |
|---|---|
| "Design a 500-agent WxCC deployment for a UAE financial services firm" | Detects HA + compliance intent · Flags UAE→Singapore DC · Triggers CBUAE and UAE PDPL flags · Generates architecture with data residency callout |
| "Migrate 1,000 Avaya agents to WxCC" | Loads Avaya→WxCC migration playbook · Runs capacity calculator · Generates phased HLD with risk register |
| "Can I deploy WxCC in mainland China?" | Hard stop before any LLM call · Returns blocker with source citation and Hong Kong alternative |
| "What's the capacity limit for concurrent IVR calls on WxCC?" | Retrieves capacity rules from Workbook D · Returns figure with source doc and knowledge date |
| "Does WxCC support HIPAA for a US healthcare contact centre?" | Loads C6 compliance pattern · Retrieves Cisco security guide chunks · Returns design constraints with BAA requirement |

---

## About

**Rajmohan Mangattu —**

This project demonstrates the methodology AbhavTech uses to build domain-specific AI systems: structured knowledge first, RAG second, model third. The WxCC SLM is the proof of concept. The methodology applies to any domain where the knowledge is structured, the stakes are high, and hallucination is not acceptable.

→ [abhavtech.com](https://abhavtech.com) · [LinkedIn](https://linkedin.com/in/rajmohan-mangattu)

---

*Knowledge current as of: 2026-07-22*
