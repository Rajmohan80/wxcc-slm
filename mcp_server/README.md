# MCP Server — 11 WxCC SLM Tools

**FastMCP server exposing deterministic consulting tools over MCP**

The MCP server is the A2A integration point. An enterprise AI orchestrator (e.g. Webex AI Agent Studio) can delegate WxCC-specific design tasks to this server as a specialised agent, receiving structured design artifacts in return.

MCP here plays the role SNMP played in network management: a standard protocol through which a management plane (the orchestrator) retrieves structured data from a specialised agent (the WxCC SLM). The analogy is not decorative — it describes the data flow exactly.

---

## Tools

| Tool | Input | Output | Knowledge source |
|---|---|---|---|
| `search_docs` | query string, folder filter, tier filter | Ranked document list with provenance | Qdrant (text search) |
| `search_vector_db` | query string, top_k, active_only | Ranked chunks with scores and metadata | Qdrant (semantic) |
| `capacity_calculator` | agent_count, aht_seconds, concurrent_ivr, codec | Seat count, bandwidth, SIP trunk sizing | Workbook D (D1–D3) |
| `generate_hld` | requirements dict | HLD document (structured markdown) | Workbook C (C2 templates) + RAG |
| `generate_lld` | hld_summary, product_selections | LLD document (detailed markdown) | Workbook C (C10 templates) + RAG |
| `export_pdf` | markdown_content, title | PDF bytes (base64) | reportlab |
| `risk_register` | scenario_type, migration_platform | Pre-populated risk register (32 risks) | Workbook D (D5) |
| `diagnose_ivr` | symptom, affected_component | Decision tree traversal + resolution | Workbook D (D9) |
| `check_compliance` | framework, country, ai_features | Applicable controls and obligations | Workbook C (C6) |
| `data_locality` | country_of_operation | DC mapping, regulations, cross-border rules | Workbook B (B12) |
| `feature_parity` | competitor_platform, feature_list | Full/Partial/No Equivalent per feature | Workbook B (B11) |

---

## Running the MCP server

```bash
# From wxcc-slm/
python mcp_server/mcp_server.py
```

The server starts on `stdio` by default (standard MCP transport). For HTTP/SSE transport (Webex AI Agent Studio integration):

```bash
python mcp_server/mcp_server.py --transport sse --port 8001
```

---

## n8n workflow exports

```
mcp_server/n8n_workflows/
├── workflow1_source_watcher.json
├── workflow2_change_triage.json
├── workflow3_apply_reindex.json
└── workflow4_golden_test_set.json
```

Import these into any n8n instance to reproduce the full Phase 7 knowledge currency loop. See [docs/phase7_n8n_spec.md](../docs/phase7_n8n_spec.md) for the full specification.

---

## A2A architecture note

LangChain builds the SLM agent. LangGraph orchestrates it as a state machine. The MCP server exposes deterministic tools that the agent calls. These are three distinct roles:

- **LangChain** — agent construction, tool binding, memory management
- **LangGraph** — state machine transitions, conditional routing, conversation persistence
- **MCP server** — deterministic tool execution (calculators, workbook lookups, document export)

The MCP protocol boundary is where the SLM becomes an agent that an external orchestrator can call. It is not a replacement for LangGraph — it is the interface through which LangGraph's outputs are made available to other agents in a multi-agent system.
