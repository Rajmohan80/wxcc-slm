# Knowledge Schema — Workbooks A–D

The four workbooks are the primary intelligence layer of the WxCC SLM. The RAG corpus retrieves evidence. The workbooks encode the rules that govern what the pipeline does with that evidence.

---

## Why workbooks, not just prompts

A prompt that says "you are a CCIE-level Cisco consultant" produces inconsistent answers. A workbook row that says:

```
Domain: WxCC  |  Scenario: UAE deployment  |  Auto_Flag_Trigger: country=UAE
→ compliance_flags = [UAE_PDPL, CBUAE]
→ SLM_Selection_Rule: DC must be SG1; verify B12 row UAE before generating design
```

produces the same answer every time, from any model, in any future version of the system. The workbook rules are version-controlled. The model's weights are not.

---

## Workbook A — Requirements Framework

**6 tabs · 348 rows**

| Tab | Contents |
|---|---|
| A1 — Domains | 15 scenario domains (WxCC, Webex Calling, CUBE/LGW, Dialogflow CX, CCAI, Control Hub, Licensing, HA/DR, Security, Compliance, Migration, Reporting, AI Features, Networking, Multi-Site) |
| A2 — Scenario Types | Per-domain scenario sub-types with required fields list |
| A3 — Required Fields | Every field the SLM must collect before generating a design. Includes `Field`, `Domain`, `Scenario`, `Required_When`, `Default_If_Not_Provided`, `Stop_If_Missing` |
| A4 — Clarification Questions | Exact question wording the SLM uses when a required field is missing. Machine-consumable. |
| A5 — Assumption Rules | Ask / Assume / Stop logic per field. Determines whether to ask the user, apply a safe default, or hard-stop. |
| A6 — Customer Discovery | 104-question checklist structured as a consulting engagement intake form. |

**Pipeline usage:** Step 3 (Requirement Completeness Check) reads A3 for the detected domain+scenario to build `missing_fields[]`. Step 5 reads A4 for the exact clarification question wording.

---

## Workbook B — Product Knowledge

**11 tabs · 478 rows**

| Tab | Contents |
|---|---|
| B1 — WxCC | Core WxCC features, capacities, limits, data locality |
| B2 — Webex Calling | Calling architecture, PSTN options, zone model |
| B3 — CUBE/LGW | Local Gateway, CUBE HA, SIP trunk design |
| B4 — Dialogflow CX | Conversational Agents capabilities, quotas, regional availability |
| B5 — Vertex AI / CCAI | Agent Assist, CCAI Insights, Vertex AI integration patterns |
| B6 — Control Hub | Provisioning, admin scope, multi-org |
| B7 — Licensing | Flex plan, per-seat vs per-use, Add-ons, India tariff |
| B8 — Release Features | Cisco release-by-release feature availability (VERIFY audit pending — see gap register) |
| B9 — Product Capabilities | Full capability matrix across WxCC feature areas |
| B10 — Known Limitations | Hard limits, known TAC issues, unsupported configurations |
| B11 — Feature Parity Matrix | WxCC vs CUCM/UCCX/UCCE/Avaya/Genesys/Amazon Connect/Five9/NICE CXone — Full/Partial/No Equivalent per feature |
| B12 — Data Locality Matrix | Country → DC → Cisco data locality table entry → applicable regulations (8 DCs: SG1, MU1, US1, US2, EU1, AU1, JP1, CA1) |

**Pipeline usage:** B11 serves the `feature_parity` MCP tool. B12 feeds Step 7 (Compliance Flag Injection). B10 informs Step 9 validation (known limitations check).

---

## Workbook C — Architecture Knowledge

**10 tabs · 254 rows**

| Tab | Contents |
|---|---|
| C1 — Architecture Patterns | Core WxCC deployment patterns with SLM selection rules |
| C2 — Reference Architectures | 18 named reference architectures (greenfield, migration, HA, multi-site, AI-enabled, etc.) |
| C3 — Migration Playbooks | 7 platform-specific migration playbooks: UCCX, UCCE, CUCM, Avaya Aura, Genesys, Amazon Connect, Five9 |
| C4 — HA/DR Patterns | High-availability and disaster recovery design patterns |
| C5 — Security Patterns | Network security, identity, and data protection patterns |
| C6 — Compliance Patterns | 7 regulatory frameworks: PCI-DSS, HIPAA, GDPR, ISO 27001, SOC 2, NIST 800-53, EU AI Act |
| C7 — Network/PSTN Patterns | PSTN option selection, QoS design, SD-WAN integration |
| C8 — Integration Patterns | CRM, WFM, analytics, and third-party integration patterns |
| C9 — AI Architecture Patterns | WxCC AI feature deployment patterns: Virtual Agent, Agent Assist, AI Concierge, CCAI (14 rows — corpus behind these rows still being built) |
| C10 — Templates | HLD, LLD, BoM, Risk Register, Assumption Log — blank templates used by the `generate_hld` and `generate_lld` MCP tools |

**Pipeline usage:** Step 8 (Architecture Generator) uses C2 reference architectures as structure for generated HLDs. Step 9 (Validation) checks generated output against C4/C5 patterns. The `check_compliance` MCP tool queries C6.

---

## Workbook D — Engineering Knowledge

**11 tabs · 414 rows**

| Tab | Contents |
|---|---|
| D1 — Capacity Planning | Agent capacity, IVR port capacity, queue sizing, overflow rules |
| D2 — Bandwidth Calculator | Per-codec bandwidth requirements, WAN sizing formulas |
| D3 — SIP Trunk Calculator | Trunk sizing, blocking probability (Erlang B/C), PSTN failover |
| D4 — HA Sizing | N+1/N+M active-standby sizing, failover time calculations |
| D5 — Risk Register | 32 pre-populated risks across design, migration, and operational categories. Each risk carries: `Auto_Flag_Trigger` (condition that raises it automatically), `Likelihood`, `Impact`, `Mitigation`. |
| D6 — Validation Checklist | 36 design validation items. Each carries: `Auto_Check_Rule` (machine-readable condition), `Severity_If_Failed`. Used by Step 9 of the pipeline. |
| D7 — Best Practices | Design best practices per domain, with rationale and Cisco source reference |
| D8 — Known TAC Issues | Documented TAC cases and known product bugs with workarounds |
| D9 — Troubleshooting Trees | 8 structured decision trees: IVR failure, call drops, audio quality, dial plan, agent state, recording, PSTN failover, API integration |
| D10 — Performance KPIs | Target KPIs for WxCC deployments: ASA, AHT, abandonment, IVR containment, FCR |
| D11 — Model Observability | Observability framework for the SLM itself: metrics, drift thresholds, golden test set structure |

**Pipeline usage:** D1–D4 power the `capacity_calculator` MCP tool. D5 is the source for the `risk_register` MCP tool (32 pre-populated entries). D9 powers the `diagnose_ivr` MCP tool. D6 is the Step 9 validation rule source.

---

## Machine-readable fields

Three field types make workbook rows directly consumable by the pipeline without natural language interpretation:

**`SLM_Selection_Rule`** — Python-evaluable condition string:
```
"country == 'UAE' AND deployment_type == 'cloud'"
→ selected_dc = 'SG1', compliance_flags.append('UAE_PDPL')
```

**`Auto_Flag_Trigger`** — Condition that raises a compliance or risk flag:
```
"ai_feature IN ['sentiment_analysis', 'emotion_detection'] AND region == 'EU'"
→ compliance_flag: EU_AI_ACT_ART5_1F (prohibited category)
```

**`Auto_Check_Rule`** — Post-generation validation condition:
```
"IF generated_design.recording_region != customer.country_of_operation:
    WARN: Recording region must match country of operation for GDPR Article 32"
```

These fields are the bridge between the structured workbooks and the automated pipeline. They are what makes this system a rules engine backed by a model, rather than a model with no guardrails.

---

## Workbook files

The workbooks are not committed to this repository — they are the proprietary knowledge layer of the system.

The schema is fully documented here. The pipeline's workbook-access layer (`knowledge/README.md`) describes the query interface.
