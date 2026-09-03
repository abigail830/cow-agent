# Required Documents — Harneys category catalog

**Category id:** `harneys`  
**Body root (`read_knowledge`):** `peripheral/required-docs/harneys/`  
**Draft source for triggers:** fee_section `solution_and_fees` (package_id, service_name, description on fee rows)

Rules below are **agent-only**. Client proposal text comes from **`content_file`** bodies only.

## Catalog

| block_id | order | content_file | include_when | exclude_when | requires_structure | append_when_any | agent_notes / post_process |
|----------|------:|--------------|--------------|--------------|:------------------:|-----------------|----------------------------|
| `individual_kyc` | 10 | `Individual KYC Requirements.md` | Any fee row `service_name` or `description` matches **Incorporation**, **Transfer-in**, or **Transfer in** | — | no | — | After reading body: **remove item 5** (Reserve Director) **and** the footnote `¹ **Reserve Director**` unless client structure is **sole individual shareholder AND sole director**. Remove the internal `Sub-Condition` blockquote if still in file. |
| `historic_corp` | 20 | `Historic Corporate Documentation.md` | Any fee row indicates **Transfer-in** / **Transfer in** | Any fee row indicates new **Incorporation** (without Transfer-in) | no | — | **Mutually exclusive** with greenfield Incorporation-only proposals. If both appear, prefer Transfer-in path and include this block; re-evaluate on package changes. |
| `bvi_architecture` | 40 | `BVI Architecture Matrix.md` | Proposal is BVI (`template_id` harneys-bvi or fee rows BVI-scoped) **and** incorporation/transfer-in style engagement | — | **yes** | — | Include `### BVI Company` only when BVI entity applies. Within it include **Individual** subsection always for natural-person stakeholders; **Corporate** only if corporate directors/shareholders exist; **Middle Layer** only if non-individual entities in ownership chain. Omit entire block if jurisdiction not BVI. |
| `cayman_architecture` | 45 | `Cayman Architecture Matrix.md` | User or facts indicate **Cayman** entity (Cayman Company or Cayman ELP) in structure | — | **yes** | — | Include only matching top-level sections (`Cayman Company` vs `Cayman Exempted Limited Partnership`). Apply same Individual / Corporate / Middle Layer filtering as BVI. |
| `kyc_closing` | 900 | `KYC closing statement.md` | — | — | no | `individual_kyc`, `historic_corp`, `bvi_architecture`, `cayman_architecture` | Append **at end** when any KYC/architecture block above is included. Always last (order 900). |

## Trigger hints (fee row fields)

When matching `include_when`, scan all fee rows:

- `source.service_name`, `source.description`, `display.preview_primary`
- `tables[].title`, `tables[].source.package_id`
- Package display names from table titles (e.g. **Approval Manager**)

Normalize case; treat `Transfer-in` and `Transfer in` as equivalent.

## Structure facts (when `requires_structure: yes`)

If not in conversation, ask minimally before composing architecture blocks:

- Jurisdictions in scope (BVI / Cayman / both)
- Individual vs corporate shareholders/directors
- Middle-layer entities in ownership tree
- Sole shareholder + sole director (for Individual KYC item 5)

May patch `facts.client` if template/draft already supports extended client fields; otherwise hold in `composition.structure` via patch:

```json
{
  "jurisdictions": ["BVI"],
  "has_corporate_stakeholders": false,
  "has_middle_layer": false,
  "sole_shareholder_sole_director": false
}
```

## Placeholder content (pending_packages)

When fee tables are empty and section is enabled:

```markdown
_Required documents will be listed once services and packages for this proposal are confirmed._
```

## Related resources

| Resource | Path |
|----------|------|
| Compose workflow (generic) | `references/required-docs-compose.md` |
| Template binding | `templates/harneys-bvi/template.yaml` → `sections[id=required_documents].knowledge` |
