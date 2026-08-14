# CounterpartyRisk — an evidence-grounded due-diligence primitive for GenLayer

A **contract-only** repository. No frontend, no server, no gateway, no simulator UI —
just the Intelligent Contract, its tests, docs, examples and deployment tooling.

`CounterpartyRisk` answers one question on-chain:

> *Is this counterparty safe enough for **this** transaction, given **this** evidence?*

A requester opens a case with a counterparty name, website, transaction context and an
explicit list of due-diligence criteria. GenLayer validators research the counterparty over
the open web and rule on whether the stated criteria were met. The ruling is a structured,
programmatically comparable object — not a vibe.

---

## Repository layout

```text
counterparty-risk/
├── contracts/
│   └── counterparty_risk.py       # the Intelligent Contract (the deliverable)
├── tests/
│   ├── conftest.py
│   └── test_counterparty_risk.py  # gltest suite: intake, allowlist, lifecycle, views
├── docs/
│   ├── ARCHITECTURE.md            # storage model, state machine, design rationale
│   ├── CONSENSUS.md               # the tiered validator, in detail
│   └── API.md                     # every public method and return shape
├── examples/
│   ├── vendor_onboarding.json     # constructor + open_case payloads
│   ├── otc_desk_kyb.json
│   └── README.md
├── scripts/
│   ├── deploy.py                  # deploy with genlayer-py
│   ├── run_case.py                # open → assess → read result
│   └── check_schema.py            # local schema/ABI sanity check before deploy
├── requirements.txt
├── LICENSE
└── .gitignore
```

---

## Why this is not "an AI decides if a company is trustworthy"

That framing is unimplementable on a blockchain: unbounded, unfalsifiable, non-reproducible.
This contract inverts it:

1. **The ruling is reduced to comparable fields.** `risk_score` (0–100), `risk_level`
   (enum), `unmet_criteria` as *indices into the case's own criteria*, and `flags` from a
   **closed vocabulary**. Validators may disagree in prose but must agree on the decision.
2. **Validator strictness is tiered by challenge round.** Round 0 is cheap and tolerant
   (score band ±15). Each challenge narrows the band (`15 → 6 → 0`) and, from round 1,
   adds an LLM-judged comparison of the *reasoning* — so matching numbers reached for
   incompatible reasons no longer count as agreement.
3. **Evidence is treated as hostile input.** Domains are allowlisted deterministically
   *before* any fetch, bodies are fenced and length-capped (6k chars/source), and the model
   is told the fenced region is untrusted data that may contain instructions to ignore.
4. **Absence of evidence is a first-class outcome.** A counterparty with no verifiable
   footprint resolves to `INSUFFICIENT_EVIDENCE`, never to `LOW`. Silence is not a clean
   bill of health.
5. **Rounds are bounded.** When the network cannot converge the case lands in `DEADLOCKED`
   and a pre-appointed reviewer settles it, recorded in the same shape as a network ruling.

## Consensus patterns demonstrated

| Pattern | Used for |
| --- | --- |
| `gl.eq_principle.strict_eq` | agreeing on the deterministic evidence manifest before any fetch |
| `gl.vm.run_nondet_unsafe` | the custom tiered validator: banded numeric agreement + exact agreement on the categorical ruling |
| `gl.nondet.exec_prompt` | validator-local reasoning comparison, applied only at challenge rounds |
| `gl.nondet.web.render` | fenced, capped, allowlisted evidence collection inside the nondet block |

---

## What the contract evaluates

Identity & business presence · operational evidence · reputation · transparency ·
suspicious or contradictory information · other material risk signals ·
**and the quality and sufficiency of the evidence itself**.

## Structured result

```json
{
  "round": 0,
  "status": 1,
  "risk_score": 62,
  "risk_level": 2,
  "risk_level_name": "HIGH",
  "flags": ["OWNERSHIP_OPAQUE", "UNVERIFIABLE_SELF_CLAIMS", "EVIDENCE_THIN"],
  "unmet_criteria": [
    { "index": 1, "criterion": "Registered legal entity verifiable in a public registry" }
  ],
  "evidence_used": ["https://example.com/", "https://sec.gov/..."],
  "reasoning": "Short, evidence-anchored explanation.",
  "ruled_by": "0x...",
  "by_reviewer": false
}
```

### Risk levels

`0 LOW` · `1 MEDIUM` · `2 HIGH` · `3 CRITICAL` · `4 INSUFFICIENT_EVIDENCE`

`INSUFFICIENT_EVIDENCE` is deliberately **not** on the LOW..CRITICAL axis. Consumers must
handle it explicitly rather than silently treating it as a pass.

### Closed flag vocabulary

`IDENTITY_UNVERIFIABLE`, `NO_BUSINESS_PRESENCE`, `SHELL_LIKE_FOOTPRINT`,
`NO_OPERATIONAL_EVIDENCE`, `OWNERSHIP_OPAQUE`, `CONTACT_DETAILS_UNVERIFIABLE`,
`REPUTATION_NEGATIVE`, `DISPUTE_OR_LITIGATION`, `REGULATORY_CONCERN`,
`CONTRADICTORY_CLAIMS`, `UNVERIFIABLE_SELF_CLAIMS`, `RECENTLY_CREATED`,
`CONTEXT_MISMATCH`, `EVIDENCE_THIN`, `EVIDENCE_UNREACHABLE`.

---

## Lifecycle

```text
CASE_OPEN --submit_evidence--> CASE_OPEN
CASE_OPEN --assess--> CASE_RULED
CASE_RULED --challenge (round < max)--> CASE_RULED     (re-ruled, tighter)
CASE_RULED --challenge (rounds exhausted OR all parties challenged)--> CASE_DEADLOCKED
CASE_DEADLOCKED --reviewer_ruling--> CASE_SETTLED
CASE_RULED --request_finalize + finalize (2 parties)--> CASE_SETTLED
```

Status codes: `0 OPEN`, `1 RULED`, `2 DEADLOCKED`, `3 SETTLED`.

## Settlement authorization

Adjudication is open; settlement is not. There is no wall clock in a deterministic VM, so
the challenge window is enforced by authorization rather than by a timestamp:

* **`challenge`** — case parties only (requester, appointed reviewer, owner), and **one
  challenge per address per case**. Escalation is expensive and terminates in
  `DEADLOCKED`, so an unbounded right to challenge would let one address grief any case
  into human settlement. The round ladder is sized to that cap
  (`MAX_ROUNDS == MAX_PARTIES == 3`), and a case also deadlocks once every *distinct* party
  has spent its challenge — so the reviewer settlement path is always reachable and no case
  can stall in `RULED` with no challenger left.
* **`request_finalize` + `finalize`** — closing a `RULED` case takes assent from two
  different parties: one requests, another confirms. The appointed reviewer (the agreed
  neutral) may finalize unilaterally, and once every challenge round is used any party may
  finalize because no dispute remains possible. Until then the counterparty holds a veto.
* Any new ruling clears a pending finalization request, so assent can never be carried
  over onto a ruling nobody agreed to close.

## Score / level invariant

Every recorded ruling — network **and** reviewer settlement — passes through the single
`_enforce_score_level` helper: `<25 LOW`, `<50 MEDIUM`, `<75 HIGH`, else `CRITICAL`, with
`INSUFFICIENT_EVIDENCE` pinned off the numeric axis at the neutral midpoint 50. A reviewer
cannot record a `CRITICAL` label against a score of 3, so consumers can safely branch on
either field alone.


---

## Quick start

### 1. Studio (fastest)

Open [GenLayer Studio](https://studio.genlayer.com), create a new contract, paste
`contracts/counterparty_risk.py`, and deploy with a constructor argument:

```json
["[\"sec.gov\",\"companieshouse.gov.uk\",\"trustpilot.com\",\"crunchbase.com\"]"]
```

The first two lines of the contract pin the toolchain and **must be kept verbatim**:

```python
# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
```

### 2. Local tooling

```sh
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python scripts/check_schema.py          # static sanity check, no network
gltest                                  # run the test suite
python scripts/deploy.py --allowlist examples/vendor_onboarding.json
python scripts/run_case.py --address 0x... --case examples/vendor_onboarding.json
```

Set `GENLAYER_RPC_URL` and `GENLAYER_PRIVATE_KEY` in the environment before deploying.

### 3. Typical call sequence

```python
open_case(
  subject_name  = "Acme Industrial Supply Ltd",
  subject_domain= "acme-industrial.example",
  context       = "Prepayment of USD 250,000 for a first-time bulk order, 60-day lead time.",
  criteria      = '["Operates a real business with verifiable customers", "Registered legal entity verifiable in a public registry", "No unresolved disputes or enforcement actions", "Ownership and control are disclosed"]',
  evidence_urls = '["https://companieshouse.gov.uk/search?q=acme+industrial"]',
  reviewer      = "0xReviewer...",
)
assess(case_id)            # round 0
challenge(case_id)         # optional, tighter each time
get_assessment(case_id)    # structured result
request_finalize(case_id)  # party A asks to close
finalize(case_id)          # party B (or the reviewer) confirms
```

`open_case` returns `None` by design (schema-stable). Read the new id from
`cases_of(requester)`.

---

## Reuse

Nothing about a domain is hardcoded. Criteria, the evidence allowlist, score thresholds and
the reviewer are case- or config-level parameters, so one deployment serves vendor
onboarding, RWA issuer checks, OTC desk KYB, grant screening, lending underwriting or DAO
treasury approval. The consensus core (`_run_round`) touches only plain strings and integers,
so it lifts into another contract with the storage layer swapped out.

## Security notes

- Only the owner can change the evidence allowlist.
- Anyone may *widen* evidence on a live case — the allowlist, not the submitter's identity,
  is what makes that safe.
- Only the case's appointed reviewer can settle a `DEADLOCKED` case.
- Fetched web content is never trusted: allowlisted, fenced, capped, and labelled untrusted.

## License

MIT — see [LICENSE](LICENSE).
