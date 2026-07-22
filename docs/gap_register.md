# Gap Register

**WxCC SLM · Known gaps, open VERIFY flags, and pending work**  
Last updated: 2026-07-22

This register exists because the architecture principle is: encode uncertainty explicitly rather than present false completeness. An interviewer or enterprise client reading this document should see a system that knows what it does not yet know.

---

## Status key

| Symbol | Meaning |
|---|---|
| 🔴 CRITICAL | Affects correctness of generated answers today |
| 🟡 MAJOR | Structural gap; does not block demo but limits production readiness |
| 🟢 MINOR | Known gap; low impact; deferred by design |
| ✅ CLOSED | Resolved |

---

## Infrastructure gaps

| ID | Gap | Status | Notes |
|---|---|---|---|
| GAP-INF-01 | No live running system | 🔴 CRITICAL | Corpus, pipeline, API, and MCP are all built. Live deployment to Cloud Run is the next action. |
| GAP-INF-02 | n8n automation not yet running | 🟡 MAJOR | Fully specified in `docs/phase7_n8n_spec.md`. n8n instance needs provisioning on GCP e2-micro. |
| GAP-INF-03 | Privacy notice for demo tool | 🟡 MAJOR | abhavtech.com/ai-hub/tools/wxcc-slm collects visitor queries. Privacy notice needed before public launch. |

---

## Knowledge gaps

| ID | Gap | Status | Workbook impact | Notes |
|---|---|---|---|---|
| GAP-KB-01 | C9 AI Architecture Patterns — 14 rows, zero corpus | 🔴 CRITICAL | C9 | AI-01…AI-05 are downloaded. C9 rows need building from these docs. |
| GAP-KB-02 | B2 Webex Calling coverage thin | 🟡 MAJOR | B2 | 68 rows: 15 India, 1 US, rest zero. Missing Operator Connect, Kari's Law, multi-site, QoS/codec, Webex Go. |
| GAP-KB-03 | B8 provenance audit needed | 🟡 MAJOR | B8 | "2024 Q2" fabrication found during Phase 2. Every date in B8 needs a source column entry before production. |
| GAP-KB-04 | B12 Data Locality — non-India rows unverified | 🔴 CRITICAL | B12 | US1 DC mapping known wrong. Full 8-DC re-verification needed. |
| GAP-KB-05 | DORA (EU financial entities) not in workbook | 🟡 MAJOR | C6 | EU-02 URL still blank. Search-derived content only. |
| GAP-KB-06 | Germany works council co-determination | 🟡 MAJOR | C6 | Real-time monitoring of German agents requires Betriebsrat approval. Not in any workbook compliance row. |
| GAP-KB-07 | Philippines BPO multi-jurisdiction pattern | 🟡 MAJOR | C7 | Common scenario (Philippines BPO serving AU/US clients). No reference architecture. |
| GAP-KB-08 | Per-country call recording consent matrix | 🟡 MAJOR | C6 | AU, NZ, SG, IN, UAE, UK all differ. Currently single-row "check local law". |
| GAP-KB-09 | Webex Calling global corpus empty | 🟡 MAJOR | B2 | `01_webex_calling/` folder has zero real documents. No Calling Design Guide, LGW Guide, or CUBE HA. |

---

## Compliance gaps

| ID | Gap | Status | Notes |
|---|---|---|---|
| GAP-COM-01 | EU AI Act Article 5(1)(f) — voice-based emotion analysis | 🔴 CRITICAL | Prohibited since Feb 2025. Not in workbook C6 compliance rows. WxCC AI Assist sentiment analysis hits this. |
| GAP-COM-02 | EU AI Act Article 50 — AI transparency disclosure | 🟡 MAJOR | Mandatory from 2 Aug 2026. The `/query` API response already includes `ai_disclosure`. Workbook C6 compliance rows need updating to reflect this obligation for contact centre deployments. |
| GAP-COM-03 | UAE PDPL cross-border transfer | ✅ CLOSED | UAE → Singapore DC triggers CBUAE + UAE PDPL. Documented in B12 + pipeline stop condition. |
| GAP-COM-04 | Article 50(2) grandfathering | 🟡 MAJOR | Digital Omnibus amendment pending OJ publication. Not yet in OJ text. Monitor EU-01. |
| GAP-COM-05 | DPDP Rules 2025 (India) | 🟡 MAJOR | C6 references the 2023 Act. 2025 Rules (subordinate legislation) not yet in workbook. Awaiting OG notification. |
| GAP-COM-06 | No AI governance framework mapping | 🟡 MAJOR | The SLM itself has no mapping to NIST AI RMF, ISO 42001, or EU AI Act risk tiers. Portfolio gap for enterprise clients. |

---

## RAG pipeline gaps

| ID | Gap | Status | Notes |
|---|---|---|---|
| GAP-RAG-01 | Embed model version not in chunk metadata | ✅ CLOSED | `4_ingest_corpus.py` writes `embed_model` and `embed_model_version` to every chunk. |
| GAP-RAG-02 | No adversarial red-team testing | 🟡 MAJOR | No evidence of prompt injection resistance, hallucination frequency, or jailbreak testing. |
| GAP-RAG-03 | No measured retrieval accuracy baseline | 🟡 MAJOR | Golden test set designed. Not yet run. No pass rate number exists. |
| GAP-RAG-04 | 3 URLs still blank in manifest | 🟢 MINOR | GC-12 (CCAI locations), EU-02 (DORA), EU-03 (2021 SCCs). Tracked in `VERSION.md`. |

---

## Corpus VERIFY flags

Open flags from corpus construction. Each must be resolved before the affected document is used to ground a production answer.

| Flag | Document | Detail |
|---|---|---|
| VERIFY-01 | CI-04 | Dated 16 Jul 2025 — predates India DC GA (Apr 2026). India content may be absent or stale. |
| VERIFY-02 | CI-08 | Path says `WxCC-10/release-1` while CI-01 is `release-2`. Possible old version. |
| VERIFY-03 | AI-05 | TAC 217186 may predate the Conversational Agents rename. Currency unverified. |
| VERIFY-04 | CL-01 | 2023 path sent originally; 2024 path confirmed later. Same session code. Record which year the downloaded file actually is. |
| VERIFY-05 | CI-10 | Path mixes `desktop_20` and `b_30`. Desktop version may be wrong. |
| VERIFY-06 | B12 non-India rows | Full DC mapping re-verification needed. US1 known wrong. |

---

## Architecture documentation gaps

| ID | Gap | Status | Notes |
|---|---|---|---|
| GAP-DOC-01 | Architect's Log not publicly visible | 🟡 MAJOR | Log v1.3 written. No public URL yet. Blocks portfolio showcase. |
| GAP-DOC-02 | Phase 7 n8n workflows not exported as JSON | 🟡 MAJOR | Spec complete. Workflow JSON files needed for `mcp_server/n8n_workflows/`. |
| GAP-DOC-03 | MkDocs site not live | 🟡 MAJOR | 44+ markdown files designed. Netlify deployment at docs.abhavtech.com pending. |

---

## What this register is NOT saying

This register lists gaps — not failures. Every gap here was identified by design, through real scenario testing or deliberate audit. The absence of a gap does not mean there are no gaps; it means none have been identified yet.

The principle behind this register: **real scenarios surface what abstract analysis misses.** The UAE flagship example (Phase 0 hero scenario) was the vehicle through which the Singapore DC mapping issue surfaced. It read as a strength in the abstract. It was a bug when tested.

---

*This document is maintained manually. The n8n automation loop (Phase 7) will produce machine-generated change register entries that feed into this document.*
