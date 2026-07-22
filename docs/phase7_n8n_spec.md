# Phase 7 — n8n Knowledge Currency Automation

**Status: In pipeline · Implementation target: post-Phase 3 validation**

**AbhavTech WxCC SLM · Knowledge Currency Specification v1.0**

---

## The problem this solves

The WxCC SLM's corpus contains 48 documents from Cisco, Google Cloud, and regulatory sources. Several of those documents change without notice:

- Cisco's data locality table (country → DC mapping) directly affects architecture decisions. An incorrect DC answer is a compliance failure.
- Dialogflow CX release notes ship weekly. A recommendation referencing a deprecated feature is a design defect.
- EU AI Act Article 50 took effect 2 August 2026. Subsequent guidance from the EU AI Office updates compliance requirements.

Without automation, corpus staleness is invisible. The SLM answers with confidence from outdated chunks. A human reviewer catches the error — or doesn't.

This Phase 7 specification defines **four n8n workflows** that close this gap: automated detection, classification, human-gated application, and regression validation. The runtime pipeline never checks the web. Knowledge currency is maintained entirely offline, on a schedule.

---

## Architecture overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                     n8n Knowledge Currency Loop                      │
│                                                                      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐ │
│  │  Workflow 1  │────▶│  Workflow 2  │────▶│     Workflow 3       │ │
│  │ Source Watch │     │Change Triage │     │ Apply & Re-index     │ │
│  │  (weekly)    │     │ (triggered)  │     │ (human-gated)        │ │
│  └──────────────┘     └──────────────┘     └──────────────────────┘ │
│                                                          │           │
│                       ┌──────────────────────────────────┘           │
│                       ▼                                              │
│              ┌──────────────────┐                                    │
│              │   Workflow 4     │                                    │
│              │  Golden Test Set │                                    │
│              │   (weekly)       │                                    │
│              └──────────────────┘                                    │
└──────────────────────────────────────────────────────────────────────┘
        │                                          │
        ▼                                          ▼
  _registry/                                Qdrant Cloud
  source_registry.json                      (active/supersedes
  change_register.jsonl                      chunk versioning)
  snapshots/{source_id}/
```

---

## Workflow 1 — Source Watcher

**Purpose:** Detect when a monitored source has changed.  
**Schedule:** Weekly, Sunday 02:00 IST  
**Cost:** Zero LLM calls. Pure HTTP + SHA-256.

### Source registry

The source registry lives at `webex_slm_corpus/_registry/source_registry.json`. It is populated at ingest time by `4_ingest_corpus.py` for every document with a live URL.

```json
{
  "SRC-001": {
    "doc_id": "CI-16",
    "title": "Webex CC Data Residency and Locality",
    "url": "https://help.webex.com/en-us/article/n0p6xa1/",
    "check_frequency": "daily",
    "last_checked": "2026-07-22T02:00:00Z",
    "last_hash": "a3383b56d2a89d15",
    "last_changed": "2026-05-27T00:00:00Z",
    "criticality": "CRITICAL",
    "feeds_workbook_tab": "B12",
    "alert_on_change": true
  }
}
```

**Criticality levels:**

| Level | Examples | n8n action on change |
|---|---|---|
| `CRITICAL` | Data locality table (CI-16), India DC article (IN-01), EU AI Act (EU-01) | Immediate Slack alert + email + block new queries on affected topic |
| `MAJOR` | Dialogflow CX release notes (GC-04), CCAI locations (GC-12) | Slack alert + queue for triage |
| `MINOR` | Cisco Live decks, overview pages | Weekly digest only |

### n8n node sequence

```
[Schedule Trigger]
    │ Cron: 0 20 * * 0 (Sunday 20:00 UTC = Monday 01:30 IST)
    ▼
[Read Source Registry]
    │ Read: _registry/source_registry.json
    │ Filter: records where check_frequency matches today's schedule
    ▼
[HTTP Request — Fetch Page]
    │ For each source: GET url
    │ Headers: User-Agent: AbhavTech-SLM-Monitor/1.0
    │ Timeout: 15s
    │ On 403/429: flag as FETCH_BLOCKED, skip hash
    ▼
[Extract Body Hash]
    │ Strip: nav, footer, cookie banners, "Was this helpful?" elements
    │ Strip method: CSS selectors matching known Cisco/GCP boilerplate patterns
    │ Hash: SHA-256 of stripped text content (UTF-8)
    │ Cost: zero LLM calls
    ▼
[Compare to Stored Hash]
    │ Load: _registry/snapshots/{source_id}/latest.txt
    │ If hash unchanged: write updated last_checked, continue
    │ If hash changed: emit change event to Workflow 2
    │ If no snapshot exists: save snapshot, treat as baseline (no change event)
    ▼
[Update Source Registry]
    │ Write: updated last_checked timestamps
    │ Append: _registry/change_register.jsonl (status entries, not just changes)
    ▼
[Weekly Summary Email]
    │ To: raj@abhavtech.com
    │ Subject: WxCC SLM — Weekly source check {date}
    │ Body: N sources checked, M changed, K fetch-blocked
```

### Change register entry (on detection)

```jsonl
{
  "event_id": "CHG-2026-07-28-001",
  "detected_at": "2026-07-28T20:14:33Z",
  "source_id": "SRC-001",
  "doc_id": "CI-16",
  "url": "https://help.webex.com/en-us/article/n0p6xa1/",
  "old_hash": "a3383b56d2a89d15",
  "new_hash": "f7c2e9b1a4d83e72",
  "criticality": "CRITICAL",
  "status": "DETECTED",
  "triage_status": "PENDING",
  "applied_at": null,
  "workbook_impact": "B12"
}
```

---

## Workflow 2 — Change Triage

**Purpose:** Classify each detected change: what changed, how significant, which workbook rows and pipeline answers are affected.  
**Trigger:** Change event from Workflow 1 (HTTP webhook or queue read)  
**Cost:** ~$0.0003 per change event (Haiku at temperature 0)

### n8n node sequence

```
[Webhook Trigger]
    │ Receives: change event from Workflow 1
    ▼
[Load Old and New Snapshots]
    │ old: _registry/snapshots/{source_id}/latest.txt (before this run)
    │ new: current fetch (already in memory from Workflow 1)
    ▼
[Diff Generation]
    │ Python function node
    │ Method: unified diff of old vs new, line-level
    │ Output: {added_lines[], removed_lines[], changed_sections[]}
    │ Cost: zero LLM calls
    ▼
[Claude Haiku Triage]
    │ Model: claude-haiku-4-5
    │ Temperature: 0
    │ Max tokens: 512
    │ Prompt:
    │   System: "You are a change triage agent for a Cisco Webex Contact Center
    │            knowledge base. Classify the significance of a document change
    │            and identify affected workbook sections. Reply ONLY in JSON."
    │   User:   "Document: {title} ({doc_id})
    │            Changed section diff:
    │            {diff_excerpt — max 800 tokens}
    │
    │            Respond with exactly this JSON:
    │            {
    │              'severity': 'CRITICAL|MAJOR|MINOR|NO_CHANGE',
    │              'change_summary': '<one sentence, what factually changed>',
    │              'affected_topics': ['data_locality', 'capacity', ...],
    │              'affected_workbook_tabs': ['B12', 'C6', ...],
    │              'pipeline_impact': '<one sentence: which query types return wrong answers>',
    │              'recommended_action': 'UPDATE_CORPUS|UPDATE_WORKBOOK|MONITOR|DISCARD'
    │            }"
    │ Output: parsed JSON (if parse fails: severity=CRITICAL, action=MANUAL_REVIEW)
    ▼
[Update Change Register]
    │ Append: triage result to existing change_register.jsonl entry
    │ Status: DETECTED → TRIAGED
    ▼
[Route by Severity]
    │ CRITICAL → Slack #wxcc-slm-alerts (immediate) + email + hold query topic
    │ MAJOR    → Slack #wxcc-slm-alerts + queue for Workflow 3
    │ MINOR    → weekly digest only; no Workflow 3 trigger
    │ NO_CHANGE → update last_checked; no further action (hash collision edge case)
    ▼
[Slack Alert — CRITICAL/MAJOR]
    │ Channel: #wxcc-slm-alerts
    │ Message:
    │   🔴 CRITICAL corpus change detected
    │   Document: Webex CC Data Residency (CI-16)
    │   Change: {change_summary}
    │   Pipeline impact: {pipeline_impact}
    │   Action required: Review and approve update
    │   → Approve: {approval_url}
    │   → View diff: {diff_url}
    │   Event: CHG-2026-07-28-001
```

### Triage output example

```json
{
  "severity": "CRITICAL",
  "change_summary": "Singapore DC (SG1) now serves Malaysia in addition to UAE and India; India moved from SG1 to Mumbai DC (MU1) effective July 2026.",
  "affected_topics": ["data_locality", "india_dc", "uae_dc", "malaysia_dc"],
  "affected_workbook_tabs": ["B12", "C6", "C7"],
  "pipeline_impact": "Queries about UAE, India, and Malaysia data residency will return wrong DC names until corpus is updated.",
  "recommended_action": "UPDATE_CORPUS"
}
```

This is the output that the gap register's Phase 7 section describes as "automated review PROPOSED, not APPLIED." The triage agent proposes. A human applies.

---

## Workflow 3 — Apply & Re-index

**Purpose:** Human-gated corpus update and Qdrant re-index.  
**Trigger:** Manual approval via Slack button or web UI  
**Design principle:** No automated write to the corpus or vector store without human review.

### n8n node sequence

```
[Webhook — Approval Received]
    │ Receives: {event_id, approved_by, approved_at}
    │ Validates: approval token matches pending change event
    ▼
[Download Updated Document]
    │ Fetch: url from source_registry
    │ Strip: boilerplate (same method as Workflow 1)
    │ Stamp: provenance header (tier, source_url, retrieved_at)
    │ Output: updated .md content
    ▼
[Write to Corpus]
    │ Overwrite: webex_slm_corpus/{folder}/{filename}.md
    │ Git commit: "chg({doc_id}): {change_summary} — approved by {approved_by}"
    │   (if repo is git-tracked locally)
    ▼
[Update Source Registry]
    │ Write: new last_hash, last_changed
    │ Save: _registry/snapshots/{source_id}/latest.txt (new snapshot)
    ▼
[Re-index via 4_ingest_corpus.py]
    │ Command: python 4_ingest_corpus.py \
    │            --corpus-dir ./webex_slm_corpus \
    │            --doc-id {doc_id} \
    │            --qdrant-url $QDRANT_URL \
    │            --qdrant-key $QDRANT_KEY
    │
    │ What the ingest script does:
    │   1. Computes SHA-256 of new content
    │   2. Loads existing Qdrant chunks for doc_id where active=true
    │   3. Sets active=false on all existing chunks (supersede, not delete)
    │   4. Embeds new content with BGE-M3
    │   5. Upserts new chunks with:
    │      active=true, supersedes=[old_point_ids], source_version=new_hash
    │   6. Returns: {new_chunks: N, superseded_chunks: M}
    ▼
[Update Change Register]
    │ Append: applied_at, applied_by, new_chunk_count, superseded_chunk_count
    │ Status: TRIAGED → APPLIED
    ▼
[Trigger Workflow 4]
    │ Run golden test set immediately after any corpus change
    │ Purpose: detect retrieval regression before users see it
    ▼
[Notify]
    │ Slack: ✅ Corpus updated: {doc_id} — {new_chunks} new chunks, {M} superseded
    │ Email: weekly digest accumulates applied changes
```

### Workbook update flag

If `recommended_action` from triage includes `UPDATE_WORKBOOK`, Workflow 3 additionally creates a GitHub issue in this repository:

```
Title: [KB-UPDATE] B12 row update required — {change_summary}
Body:  Event: {event_id}
       Document: {doc_id} ({title})
       Affected tabs: {affected_workbook_tabs}
       Change: {change_summary}
       Triage classification: {severity}
       Action required: Review and update affected workbook rows,
                        then re-run 4_ingest_corpus.py to refresh metadata.
Labels: knowledge-base, needs-review
```

This is the link between automated corpus updates and manual workbook maintenance. Workbook rows are not auto-updated — human expert review is required to change structured knowledge.

---

## Workflow 4 — Golden Test Set

**Purpose:** Detect retrieval and generation quality degradation after corpus changes or model updates.  
**Schedule:** Weekly, Sunday 03:00 IST (after Workflow 1 completes); also triggered by Workflow 3 after any corpus update.  
**Cost:** ~$0.03–0.10 per run (50 test cases × Haiku + small Sonnet sample)

### Golden test set structure

50 curated Q&A pairs covering all 15 scenario domains from Workbook A. Located at `notebooks/golden_test_set.json`.

```json
{
  "test_id": "GT-001",
  "scenario_domain": "data_residency",
  "query": "Where does a UAE customer's Webex Contact Center data reside?",
  "expected_dc": "Singapore (SG1)",
  "expected_regulation_flags": ["UAE_PDPL", "CBUAE"],
  "expected_sources_contain": ["CI-16"],
  "expected_stop_condition": null,
  "criticality": "CRITICAL",
  "last_passed": "2026-07-22",
  "last_failed": null
}
```

Test categories:

| Category | Count | What it validates |
|---|---|---|
| Data residency (per country) | 10 | B12 DC mapping is current |
| Stop conditions | 5 | Hard blockers trigger correctly |
| Compliance flags | 8 | Correct regulations raised per scenario |
| Capacity calculations | 5 | Workbook D formulas return correct figures |
| Migration scenarios | 7 | Correct migration playbook retrieved |
| Feature queries | 8 | B11 feature parity matrix retrieved accurately |
| AI/compliance edge cases | 7 | EU AI Act Art 5/50 flags trigger correctly |

### n8n node sequence

```
[Schedule / Webhook Trigger]
    ▼
[Load Golden Test Set]
    │ Read: notebooks/golden_test_set.json
    │ Filter: run all 50; or filter by criticality if post-corpus-update run
    ▼
[For Each Test Case]
    │ POST to /query endpoint: {query: test.query, top_k: 8}
    │ Capture: {answer, sources, compliance_flags, stop_condition, latency_ms}
    ▼
[Evaluate Results]
    │ For each test:
    │   PASS if all of:
    │     expected_dc in answer (if set)
    │     expected_regulation_flags ⊆ response.compliance_flags
    │     expected_sources_contain ⊆ [s.doc_id for s in response.sources]
    │     expected_stop_condition == response.stop_condition
    │   FAIL otherwise; record: {test_id, actual_answer, actual_sources, diff}
    ▼
[Compute Metrics]
    │ pass_rate: passed / total
    │ critical_pass_rate: critical tests passed / critical total
    │ avg_latency_ms
    │ p95_latency_ms
    │ source_recall: correct sources retrieved / expected sources
    ▼
[Write Results to MLflow]
    │ Run name: golden-test-{date}
    │ Metrics: pass_rate, critical_pass_rate, avg_latency_ms, source_recall
    │ Artifact: full results JSON
    ▼
[Alarm Conditions]
    │ CRITICAL alarm if:
    │   critical_pass_rate < 1.0  (any critical test fails)
    │
    │ MAJOR alarm if:
    │   pass_rate < 0.90 (more than 5 of 50 fail)
    │   OR avg_latency_ms > 5000
    │
    │ MODEL CHANGE trigger if:
    │   pass_rate drops > 5 percentage points vs previous week's run
    │   (signals model behaviour drift; consider V2 fine-tuning)
    ▼
[Slack — on alarm]
    │ 🔴 Golden test CRITICAL alarm
    │    Critical pass rate: {rate}%
    │    Failed tests: {test_ids}
    │    Likely cause: {most_recent_corpus_change or model_update}
    │    Action: review failed test details in MLflow
    ▼
[Update golden_test_set.json]
    │ Write: last_passed / last_failed per test case
```

### Stale-critical alarm

A separate check runs within Workflow 4:

```
For each test where criticality=CRITICAL:
    If last_passed < (today - 14 days):
        → STALE_CRITICAL alarm
        → Slack: ⚠️ Critical test GT-001 has not passed in 14 days.
                    Last passed: {date}. Manual review required.
```

This catches the failure mode where a critical test is not run (skipped by logic error) rather than failing.

---

## Runtime pipeline integration

The n8n automation loop runs entirely offline. The runtime pipeline integrates with it at two points:

**1. Knowledge-current-as-of footer stamp**

Every `/query` response includes:

```json
"knowledge_date": "2026-07-22"
```

This date comes from `source_registry.json` — specifically, the `min(last_changed)` across all documents that contributed chunks to the response. It is not the ingest date. It is not today's date. It is the date of the most recently updated source that the response draws on.

**2. Pending-change inline flag**

If any source contributing to a response has a change register entry with `status=TRIAGED` (detected and classified, but not yet applied), the response includes:

```json
"knowledge_currency_warning": "One or more sources for this response have a pending update under review. Verify critical figures against current Cisco documentation before implementation."
```

This is the "honest-uncertainty inline flag" described in the gap register. It does not suppress the response. It marks it.

---

## n8n infrastructure

**Deployment:** Self-hosted n8n on GCP e2-micro (free tier)  
**n8n version:** 1.x (community edition)  
**Credential storage:** n8n built-in encrypted credential store (never `.env`)

**Required credentials in n8n:**

| Credential | Used by |
|---|---|
| Anthropic API key | Workflow 2 (Haiku triage) |
| Qdrant URL + API key | Workflow 3 (re-index) |
| Slack Bot token | Workflows 2, 3, 4 (alerts) |
| Email (SMTP) | Workflow 1, 4 (digests) |
| GitHub token | Workflow 3 (issue creation) |

**Workflow files:** Exported as JSON and committed to `mcp_server/n8n_workflows/` in this repository. Import into any n8n instance to reproduce the full automation loop.

---

## Implementation checklist

- [ ] n8n instance running on GCP e2-micro
- [ ] Source registry populated by `4_ingest_corpus.py` at ingest time
- [ ] Workflow 1 imported and scheduled
- [ ] Workflow 2 imported; Haiku credential configured
- [ ] Workflow 3 imported; approval webhook URL confirmed
- [ ] Workflow 4 imported; golden test set at `notebooks/golden_test_set.json`
- [ ] Slack `#wxcc-slm-alerts` channel created and bot invited
- [ ] MLflow tracking server running (or use MLflow Cloud free tier)
- [ ] `/query` endpoint returns `knowledge_date` and `knowledge_currency_warning`
- [ ] First full regression run completed; baseline pass rate recorded

---

*Specification version 1.0 · July 2026 · Status: in pipeline*
