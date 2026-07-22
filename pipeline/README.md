# Pipeline — 9-Step Intent Flow

**LangChain + LangGraph state machine for structured consulting reasoning**

---

## Files

| File | Role |
|---|---|
| `slm_pipeline.py` | Top-level pipeline — the 9-step state machine entry point |
| `query_engine.py` | Qdrant retrieval: semantic search with provenance-tier ranking |
| `prompt_builder.py` | System prompt + per-step classification prompt assembly |

---

## Running

```bash
# Single query
python -m pipeline.slm_pipeline "Where does a UAE customer's WxCC data reside?"

# With conversation history (JSON file)
python -m pipeline.slm_pipeline "How many SIP trunks do I need?" \
    --history history.json
```

---

## The 9 steps

```
1  Intent Classifier     → intent ∈ {architecture_design, capacity_planning,
                            migration, troubleshooting, compliance_check,
                            feature_query, general_info}

2  Scenario Detector     → scenario ∈ {greenfield, migration, HA_DR,
                            security_hardening, AI_enablement, multi_site,
                            compliance_audit}

3  Requirement Check     → missing_fields[] from Workbook A

4  Stop Condition        → hard-coded rules; runs before ANY generation call

5  Missing Info Gate     → ask OR proceed

6  RAG Retrieval         → Qdrant, top_k=8, active=true, tier-ranked

7  Compliance Injection  → country → DC → flags from B12

8  Architecture Generate → Claude Sonnet 4.6 with cached system prompt

9  Validation            → Workbook D D6 rules; post-generation warnings
```

Steps 1–7 use Claude Haiku 4.5 with a prompt-cached system prompt (~$0.0003/query). Step 8 uses Sonnet 4.6 (~$0.003–0.015/query depending on length).

---

## SLMResponse schema

```python
@dataclass
class SLMResponse:
    answer:                  str
    intent:                  str
    domain:                  str
    compliance_flags:        list[str]
    stop_condition:          Optional[str]
    missing_fields:          list[str]
    sources:                 list[dict]          # doc_id, tier, score, url
    clarification_needed:    bool
    clarification_question:  Optional[str]
    latency_ms:              int
    tokens_used:             dict                # fast_in, fast_out, main_in, main_out
    knowledge_date:          str                 # YYYY-MM-DD, min(last_changed) of sources
    knowledge_currency_warning: Optional[str]    # set if pending unapplied change exists
    model_used:              str
```
