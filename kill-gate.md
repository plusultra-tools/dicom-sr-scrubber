# Kill Gate — dicom-sr-scrubber

**Venture**: dicom-sr-scrubber
**Launch date**: 2026-05-15
**Kill decision date**: d+30 = 2026-06-14
**Phase 2 opt-in window**: d+60 = 2026-07-14

---

## Go signal (ANY ONE is sufficient to proceed to Phase 2)

| Signal | Threshold | Measurement |
|--------|-----------|-------------|
| GitHub stars | ≥ 25 | Check repo stars at d+30 |
| PyPI last-week installs | ≥ 10 | pip stats or pypistats.org |
| Real-affiliation issues | ≥ 2 | GitHub Issues from users with institution emails or credible profiles |
| Commercial inbound | ≥ 1 by d+60 | Any email/DM expressing willingness to pay or trial the hosted version |

"Real-affiliation" = GitHub profile shows hospital, university, or medtech employer OR issue cites a specific PACS/IRB workflow.

---

## Kill criteria

Unconditional kill at d+30 if ALL of the following are true:
- Stars < 5
- No issues opened by non-principal accounts
- No mentions on r/medicalimaging, dev.to, HN, or awesome-dicom
- No responses to distribution posts (if any were made under §12 approval)

---

## Yellow zone (defer kill to d+60)

Kill deferred to d+60 if:
- Stars 5–24 AND at least 1 organic issue OR
- Installs 5–9 last-week OR
- dcm-anon users refer to this tool in any channel

In yellow zone: do NOT invest further build time; wait for the d+60 check.

---

## Phase 2 conditions (integration into dcm-anon hosted tier)

Phase 2 = integrate `dicom-sr-scrubber` as a premium add-on inside the
`dcm-anon` hosted batch pipeline. Trigger Phase 2 only if:
1. Go signal met AND
2. dcm-anon Phase 2 plan exists (hosted vault with Stripe billing) AND
3. ≥ 1 commercial inbound specifically for the SR scrubbing feature by d+60.

Phase 2 pricing: €19–29/mo bundled with dcm-anon hosted tier.

---

## Distribution plan (§12 approval required before execution)

- `r/medicalimaging` — "I built a pure-Python DICOM SR PHI scrubber for the gap dcm-anon explicitly skips"
- dev.to post — walkthrough with synthetic SR example
- PR to awesome-dicom list
- Cross-link from dcm-anon README (dcm-anon team = principal; no approval gate)
- Direct outreach to ≥3 radiology informatics groups on GitHub (read Issues, identify users with SR-related questions)

---

## Post-mortem on red

If killed: document in `archive/dicom-sr-scrubber/post-mortem.md`:
- Actual signals received
- Hypothesis on why demand did not materialise (e.g. CTP already covers the use case for the target audience, Python-only constraint is too restrictive, etc.)
- Recycled code / learnings for portfolio
