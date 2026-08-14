# Consensus

## The problem

Two honest validators researching the same counterparty will never produce the same prose.
If agreement means "same text", nothing ever finalises. If agreement means "an LLM thinks
these are vaguely similar", the contract has no decision surface at all.

## The answer: a comparable ruling

Every round produces exactly this object:

| Field | Type | Comparison |
| --- | --- | --- |
| `risk_score` | int 0–100 | banded, tolerance depends on round |
| `risk_level` | enum 0–4 | **exact** |
| `unmet_criteria` | set of criterion indices | **exact set** |
| `flags` | set of indices into a closed vocabulary | **exact set** |
| `evidence_used` | list of URLs | informational |
| `reasoning` | short prose | judged only from round 1 on |

Validators may write completely different reasoning and still agree, provided the decision
matches.

## Tiering by round

```python
MAX_PARTIES = 3                      # requester, reviewer, owner
SCORE_TOLERANCE_BY_ROUND = [15, 6, 0]
PROSE_COMPARISON_FROM_ROUND = 1
MAX_ROUNDS = 3                       # == MAX_PARTIES, asserted at import
```

| Round | Score band | Reasoning compared? | Intent |
| --- | --- | --- | --- |
| 0 (`assess`) | ±15 | no | cheap, tolerant first pass |
| 1 (`challenge`) | ±6 | yes | someone disputes; require compatible logic |
| 2 (`challenge`) | ±0 | yes | last resort: exact agreement before deadlock |

The ladder length is not free. Only the three case parties may challenge and each may
challenge once, so at most three challenges can ever be made: challenge #1 runs round 1,
#2 runs round 2, #3 exhausts the ladder and deadlocks. A longer ladder would make
`DEADLOCKED` — and therefore `reviewer_ruling` — unreachable, which is why
`MAX_ROUNDS == MAX_PARTIES` is asserted at import time.

Escalation is part of the consensus rule, not an off-chain process. A challenger cannot pick
the standard; the round does.

## Mechanics

1. **Manifest agreement — `gl.eq_principle.strict_eq`.** The evidence manifest (subject,
   normalised host, ordered allowlisted URLs, round) is computed deterministically and
   agreed exactly *before* any fetch. Validators cannot be pointed at different evidence.

2. **Leader run — `gl.vm.run_nondet_unsafe`.** The leader renders the allowlisted pages,
   builds the fenced prompt, and returns normalised ruling JSON.

3. **Validator run.** Each validator repeats the work independently and then compares:

   ```text
   accept ⟺ |score_v − score_leader| ≤ tolerance[round]
            ∧ level_v == level_leader
            ∧ set(unmet_v) == set(unmet_leader)
            ∧ set(flags_v) == set(flags_leader)
            ∧ (round < 1 ∨ reasoning_compatible(prose_v, prose_leader))
   ```

4. **Reasoning comparison — `gl.nondet.exec_prompt`.** From round 1, the validator asks a
   model whether the two explanations rest on compatible findings — catching the case where
   the same number was reached for contradictory reasons. It is a *validator-local* judgment
   on two strings, never a re-litigation of the case.

5. **Deadlock.** Rounds are bounded and the bound is *reachable*. `DEADLOCKED` is set
   either when the ladder is exhausted or when every distinct case party has already spent
   its single challenge (parties may overlap, e.g. requester == owner), so a case is never
   left in `RULED` with nobody able to dispute it. Once deadlocked, the
   pre-appointed reviewer records a ruling in the identical shape via `reviewer_ruling`, so
   consumers read one interface either way.

## Why `INSUFFICIENT_EVIDENCE` is off the axis

If a thin footprint collapsed to `LOW`, the contract would reward invisibility — exactly the
profile of a fresh shell. It is a fifth, non-ordinal value so integrators must branch on it
instead of treating silence as a pass. `EVIDENCE_THIN` and `EVIDENCE_UNREACHABLE` carry the
reason.

## Determinism inventory

Deterministic (identical across validators): allowlist normalisation, URL gating, manifest,
index bounding, score clamping, score→level fallback, storage writes.

Non-deterministic (inside nondet blocks only): page rendering, model reasoning, the
reasoning-compatibility judgment.
