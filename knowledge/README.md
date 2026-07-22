# Knowledge Layer

The four workbooks (A–D) are the primary intelligence layer of the WxCC SLM.

They are not committed to this repository. Full schema documentation: [docs/knowledge_schema.md](../docs/knowledge_schema.md)

## What lives here

```
knowledge/
└── README.md    ← this file
```

In a production deployment, this directory contains the four Excel workbooks:

```
knowledge/
├── AbhavTech_WxCC_SLM_Workbook_A_Requirements.xlsx   # 348 rows, 6 tabs
├── AbhavTech_WxCC_SLM_Workbook_B_Product.xlsx        # 478 rows, 11 tabs
├── AbhavTech_WxCC_SLM_Workbook_C_Architecture.xlsx   # 254 rows, 10 tabs
└── AbhavTech_WxCC_SLM_Workbook_D_Engineering.xlsx    # 414 rows, 11 tabs
```

The pipeline accesses them via `openpyxl` at startup, loading structured rules into memory. No workbook content is embedded into model prompts directly — rows are retrieved by lookup against domain/scenario keys, not by semantic search.

## How the pipeline uses workbooks

```python
# Step 3 — Requirement Completeness Check (simplified)
required = workbook_a.get_required_fields(intent="architecture_design", domain="wxcc")
missing = [f for f in required if f not in user_inputs]

# Step 9 — Validation (simplified)
rules = workbook_d.get_validation_rules(scenario_type="migration")
for rule in rules:
    if rule.evaluate(generated_design):
        response.warnings.append(rule.warning_message)

# MCP tool — capacity_calculator
formula = workbook_d.get_capacity_formula(calc_type="agent_seats")
result = formula.evaluate(inputs={"concurrent_calls": 500, "aht_seconds": 240})
```

## Proprietary content notice

The workbooks are the proprietary knowledge layer of this system and are not committed to this repository.
