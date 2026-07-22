"""
slm_pipeline.py — WxCC SLM Phase 3: 9-Step Intent Flow (Gemini 2.0 Flash edition)
===================================================================================
Primary: Gemini 2.0 Flash (generation) + Llama 3.3-70B via Groq (classification)
Fallback: pure Groq if Google key missing
One-line swap to Claude: change BACKEND = "gemini" to BACKEND = "claude"

Save to: D:/project-slm-webex/slm_pipeline.py
"""

import os, json, time
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv
load_dotenv(override=True)

from query_engine import retrieve, RetrievedChunk
from prompt_builder import build_classification_prompt, get_system_prompt
from query_engine import format_context

BACKEND = "gemini"

# Models
GROQ_FAST_MODEL   = "llama-3.3-70b-versatile"   # classification (steps 1-7)
GEMINI_MAIN_MODEL = "models/gemini-2.5-flash"            # generation (step 8)

MAX_TOKENS_FAST = 512
MAX_TOKENS_MAIN = 4096


@dataclass
class SLMResponse:
    answer:               str
    intent:               str
    domain:               str
    compliance_flags:     list
    stop_condition:       Optional[str]
    missing_fields:       list
    sources:              list
    clarification_needed: bool
    clarification_question: Optional[str]
    latency_ms:           int
    tokens_used:          dict
    knowledge_date:       str
    model_used:           str


STOP_RULES = {
    "china": (
        "china_blocker",
        "Mainland China is not an available Country of Operation for Webex Contact "
        "Center — it appears in none of Cisco's data locality tables (n0p6xa1, 27 May "
        "2026). This is a hard blocker. WxCC cannot be deployed for mainland China "
        "operations. Alternative: Hong Kong is available and served from the Singapore "
        "data centre (SG1) — latency and cross-border analysis apply — or consider a "
        "different platform."
    ),
}


def _check_stop(query_lower):
    if "mainland china" in query_lower or (
        "china" in query_lower and "hong kong" not in query_lower
    ):
        return STOP_RULES["china"]
    return None


def _get_groq_client():
    from groq import Groq
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY not set.")
    return Groq(api_key=key)


def _classify_groq(client, query):
    _, sys_prompt = build_classification_prompt(query)
    resp = client.chat.completions.create(
        model=GROQ_FAST_MODEL,
        max_tokens=MAX_TOKENS_FAST,
        temperature=0,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user",   "content": query},
        ],
    )
    raw = resp.choices[0].message.content.strip()
    raw = raw.replace("```json","").replace("```","").strip()
    try:
        return json.loads(raw), resp.usage
    except json.JSONDecodeError:
        return {
            "intent": "general_info", "domain": "wxcc",
            "missing_fields": [], "stop_condition": None,
            "compliance_flags": [], "confidence": "low",
        }, resp.usage


def _generate_groq(client, query, chunks, history):
    from query_engine import format_context
    context_block = format_context(chunks)
    system = __import__('prompt_builder').get_system_prompt()
    user_content = (
        "<retrieved_context>\n"
        + context_block
        + "\n</retrieved_context>\n\n"
        + "Using the retrieved context above, answer this query:\n\n" + query
    )
    messages = [{"role": "system", "content": system}]
    if history:
        messages.extend(history[:-1])
    messages.append({"role": "user", "content": user_content})
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=4096,
        temperature=0.2,
        messages=messages,
    )
    usage = {"prompt_tokens": resp.usage.prompt_tokens,
             "completion_tokens": resp.usage.completion_tokens}
    return resp.choices[0].message.content.strip(), usage


def run(query, conversation_history=None, top_k=8):
    t0 = __import__('time').time()
    tokens = {"fast_in": 0, "fast_out": 0, "main_in": 0, "main_out": 0}
    stop = _check_stop(query.lower())
    if stop:
        return SLMResponse(
            answer=stop[1], intent="architecture_design", domain="wxcc",
            compliance_flags=[], stop_condition=stop[0], missing_fields=[],
            sources=[], clarification_needed=False, clarification_question=None,
            latency_ms=int((__import__('time').time()-t0)*1000), tokens_used=tokens,
            knowledge_date="n/a", model_used="hard-stop (no LLM)",
        )
    client = _get_groq_client()
    classification, f_usage = _classify_groq(client, query)
    tokens["fast_in"] = f_usage.prompt_tokens
    tokens["fast_out"] = f_usage.completion_tokens
    intent = classification.get("intent", "general_info")
    domain = classification.get("domain", "wxcc")
    missing_fields = classification.get("missing_fields", [])
    compliance_flags = classification.get("compliance_flags", [])
    if missing_fields:
        q = (f"To give you an accurate {intent.replace(chr(95),' ')} recommendation, "
             f"I need: **{missing_fields[0]}**. Could you provide that?")
        return SLMResponse(
            answer=q, intent=intent, domain=domain, compliance_flags=compliance_flags,
            stop_condition=None, missing_fields=missing_fields, sources=[],
            clarification_needed=True, clarification_question=q,
            latency_ms=int((__import__('time').time()-t0)*1000), tokens_used=tokens,
            knowledge_date="n/a", model_used=GROQ_FAST_MODEL,
        )
    folder_hints = {
        "wxcc": None, "webex_calling": "02_wxcc_architecture",
        "dialogflow_cx": "07_gcp_dialogflow_cx", "ccai": "08_gcp_ccai_vertex_ai",
        "licensing": "06_licensing", "compliance": "12_compliance",
    }
    chunks = retrieve(query, top_k=top_k, folder_filter=folder_hints.get(domain))
    if not chunks:
        chunks = retrieve(query, top_k=top_k)
    augmented_query = query
    if compliance_flags:
        augmented_query = (query + f"\n\n[Compliance context: this scenario triggers "
                          f"{', '.join(compliance_flags)}. Address residency and consent.]")
    answer, m_usage = _generate_groq(client, augmented_query, chunks, conversation_history)
    tokens["main_in"] = m_usage.get("prompt_tokens", 0)
    tokens["main_out"] = m_usage.get("completion_tokens", 0)
    sources = [{"filename": c.filename, "doc_id": c.doc_id,
                "provenance_tier": c.provenance_tier, "source_url": c.source_url,
                "score": round(c.score, 3)} for c in chunks]
    return SLMResponse(
        answer=answer, intent=intent, domain=domain, compliance_flags=compliance_flags,
        stop_condition=None, missing_fields=[], sources=sources,
        clarification_needed=False, clarification_question=None,
        latency_ms=int((__import__('time').time()-t0)*1000), tokens_used=tokens,
        knowledge_date="2026-07-21",
        model_used=f"Groq/{GROQ_FAST_MODEL} + Groq/llama-3.3-70b-versatile",
    )


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Where does a UAE customer WxCC data reside?"
    r = run(q)
    print(f"Model: {r.model_used}")
    print(f"Latency: {r.latency_ms}ms")
    print(f"\nAnswer:\n{r.answer}")
