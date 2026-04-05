# Drug Explorer — Displayed Fields

## Drug Row (collapsed)
- Drug Name (e.g. "Riabni", "Rituximab")
- Payer badges (e.g. "BCBS NC", "Cigna")
- Policy count
- Last updated date
- Action icons: Compare (grid icon), View Details (document icon)

## Expanded — Policy Document Header
- Payer name (e.g. "BCBS NC", "Cigna")
- Document title (e.g. "Corporate Medical Policy", "Rituximab Intravenous Products for Non-Oncology Indications")
- Extraction status badge (`complete`, `review_required`)
- Plan type (e.g. "Commercial")
- Effective date (e.g. "2026-04-16")
- Indications count (e.g. "Indications: 2")

## Expanded — Per-Indication Criteria
- **Indication name** (e.g. "Rituxan (rituximab)", "Rheumatoid arthritis")
- **Benefit type** badge (e.g. "medical")
- **Approval phase** badge (e.g. "continuation 1", "continuation 2plus", "initial")
- **Covered status** badge (e.g. "covered")
- **Needs review** badge (when flagged)
- **ICD-10 code** (e.g. "ICD-10: M06.9")
- **Confidence score** (e.g. "90% conf", "60% conf")
- **Initial Auth Criteria** — list of requirements with logic operators:
  - e.g. "AND — Patient has received one prior course of therapy."
  - e.g. "AND — Patient has moderately to severely active disease."
  - e.g. "AND — Patient has had an inadequate response to one or more tumor necrosis factor inhibitors."
- **Dosing** — regimen with indication context:
  - e.g. "In combination with methotrexate — Rheumatoid arthritis"
- **Universal Criteria** — bullet list:
  - e.g. "Indication is listed in Table 1 AND criteria are met"
  - e.g. "Dose at or below the threshold"
  - e.g. "Biosimilar step therapy (non-preferred products require Mvasi or Zirabev trial first)"
- **Preferred products** — green-highlighted pills (e.g. "Mvasi", "Zirabev")
- **Brand names** — grey pills (e.g. "Rituxan", "Riabni", "Ruxience", "Truxima")
- **Review Reasons** — amber warning box:
  - e.g. "Missing initialAuthDurationMonths"
  - e.g. "Cigna preferredProducts empty — companion PSM document not merged"

## Expanded — Footer Actions
- Refresh criteria button
- Delete policy button (trash icon)
