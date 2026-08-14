# API

All amounts are integers. All list-valued inputs are **JSON strings**, which keeps the
contract schema flat and unambiguous.

## Constructor

```python
CounterpartyRisk(allowed_domains: str)
```

`allowed_domains` — JSON array of bare hosts evidence URLs may come from, e.g.
`["sec.gov","companieshouse.gov.uk","trustpilot.com"]`. A case's own subject domain is
always permitted for that case.

## Write methods

### `set_allowed_domains(allowed_domains: str) -> None`
Owner only. Replaces the evidence allowlist.

### `open_case(subject_name, subject_domain, context, criteria, evidence_urls, reviewer) -> None`
| Param | Type | Meaning |
| --- | --- | --- |
| `subject_name` | `str` | legal or trading name of the counterparty (person or company) |
| `subject_domain` | `str` | primary website host; `""` if genuinely none |
| `context` | `str` | the transaction this risk call is *for* |
| `criteria` | `str` | JSON array of explicit due-diligence criteria (max 16); rulings reference these by index |
| `evidence_urls` | `str` | JSON array of starting evidence URLs (allowlist-checked, max 12) |
| `reviewer` | `str` | address that settles the case if the network deadlocks |

Returns `None`. Read the new id with `cases_of(requester)`.

### `submit_evidence(case_id: u256, url: str) -> None`
Adds one allowlisted URL while the case is `OPEN` or `RULED`. Open to any sender.

### `assess(case_id: u256) -> None`
Runs round 0. Requires status `OPEN`. Produces the first ruling and opens the challenge
window (`RULED`).

### `challenge(case_id: u256) -> None`
Re-runs the assessment under a strictly tighter validator. Requires status `RULED`. The
case becomes `DEADLOCKED` instead when the round ladder is exhausted **or** when every
distinct case party has already spent its single challenge. Since `MAX_ROUNDS == MAX_PARTIES
== 3`, three challenges from the three parties always reach `DEADLOCKED`.

Authorized: requester, appointed reviewer, or owner — **one challenge per address per
case**. Clears any pending finalization request.

### `reviewer_ruling(case_id, risk_score, risk_level, flag_indices, unmet_indices, reasoning) -> None`
Appointed reviewer only, `DEADLOCKED` only. `flag_indices` and `unmet_indices` are JSON
arrays of integers. Recorded in the same shape as a network ruling, then `SETTLED`.
The submitted `risk_score`/`risk_level` pair is passed through the same
`_enforce_score_level` invariant as a network ruling, so a reviewer cannot publish a level
the contract's own mapping contradicts.

### `request_finalize(case_id: u256) -> None`
Case parties only (requester, reviewer, owner), status `RULED`. Records intent to close;
does not close. Overwritten by later requests and cleared by any new ruling.

### `finalize(case_id: u256) -> None`
Case parties only, status `RULED`. Permitted when the sender is the appointed reviewer, or
all challenge rounds are exhausted, or a **different** party already called
`request_finalize`. The standing ruling becomes terminal (`SETTLED`).

## View methods

### `config()`
Owner, allowlist, `risk_flags`, `risk_levels`, `max_rounds`, `score_tolerance_by_round`,
`prose_comparison_from_round`, `max_parties`, evidence limits.

### `get_case(case_id)`
`id`, `requester`, `subject_name`, `subject_domain`, `context`, `criteria`,
`evidence_urls`, `reviewer`, `challengers`, `challenges_remaining`,
`finalize_requested_by`, `status`, `round_index`, `rounds_recorded`,
`challenges_remaining` (challenges that still yield a network ruling), `unspent_challengers`
(distinct parties that have not challenged yet).

### `get_assessment(case_id)`
The standing (latest) ruling, expanded. `{"case_id", "status", "ruling": null}` when no
ruling exists yet.

```json
{
  "round": 1,
  "status": 1,
  "risk_score": 62,
  "risk_level": 2,
  "risk_level_name": "HIGH",
  "flags": ["OWNERSHIP_OPAQUE", "EVIDENCE_THIN"],
  "unmet_criteria": [{ "index": 1, "criterion": "..." }],
  "evidence_used": ["https://..."],
  "reasoning": "...",
  "ruled_by": "0x...",
  "by_reviewer": false
}
```

### `get_rulings(case_id)`
Full append-only history in the same expanded shape — shows how the network moved, not just
where it landed.

### `cases_of(requester: str)`
Case ids opened by an address.

## Enums

Status: `0 OPEN`, `1 RULED`, `2 DEADLOCKED`, `3 SETTLED`.

Risk level: `0 LOW`, `1 MEDIUM`, `2 HIGH`, `3 CRITICAL`, `4 INSUFFICIENT_EVIDENCE`.

Score → level mapping is an invariant applied to **every** recorded ruling, network or
reviewer: `<25 LOW`, `<50 MEDIUM`, `<75 HIGH`, else `CRITICAL`. `INSUFFICIENT_EVIDENCE` is
off the numeric axis and its score is pinned to the neutral midpoint `50`.

## Limits

`MAX_CRITERIA = 16` · `MAX_EVIDENCE_URLS = 12` · `MAX_EVIDENCE_BODY_CHARS = 6000` ·
`MAX_TEXT_FIELD = 2000` · `MAX_ROUNDS = 3` · `MAX_PARTIES = 3`.
