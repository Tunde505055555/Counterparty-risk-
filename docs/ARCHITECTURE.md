# Architecture

## Design stance

The contract does not ask a model "is this company trustworthy?". It asks the network to
rule on a **bounded, comparable object** derived from evidence the contract itself gated.
Everything below follows from that stance.

## Storage model — primitives only

```python
@allow_storage
@dataclass
class Case:
    requester: Address
    subject_name: str
    subject_domain: str     # bare host, e.g. "example.com"
    context: str
    criteria_json: str      # JSON array; indices are the consensus surface
    evidence_json: str      # JSON array of allowlisted https URLs
    reviewer: Address       # settles a DEADLOCKED case
    status: u8
    round_index: u8
```

```python
class CounterpartyRisk(gl.Contract):
    owner: Address
    allowed_domains_json: str
    next_case_id: u256
    cases: TreeMap[u256, Case]
    rulings: TreeMap[u256, DynArray[str]]      # append-only, one JSON blob per round
    cases_by_requester: TreeMap[Address, DynArray[u256]]
```

Two rules kept the schema stable:

1. **No nested collections inside a stored dataclass.** The ruling history lives in a
   top-level `TreeMap[u256, DynArray[str]]` keyed by case id, not inside `Case`.
2. **Public signatures use only `str` and `u256`/`u8`.** Lists cross the boundary as JSON
   strings; `open_case` returns `None`.

The header lines pin the toolchain and must be kept verbatim:

```python
# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
```

The class must inherit `gl.Contract` (no `@gl.contract` decorator in v0.2.16).

## State machine

```text
CASE_OPEN --submit_evidence--> CASE_OPEN
CASE_OPEN --assess--> CASE_RULED
CASE_RULED --challenge (round < max)--> CASE_RULED
CASE_RULED --challenge (rounds exhausted)--> CASE_DEADLOCKED
CASE_DEADLOCKED --reviewer_ruling--> CASE_SETTLED
CASE_RULED --request_finalize + finalize (2 parties)--> CASE_SETTLED

Settlement is authorized, not open: see README > Settlement authorization.
```

## Evidence pipeline

```text
open_case / submit_evidence
        │  https only, host normalised, allowlist ∪ {subject domain}
        ▼
deterministic manifest ──gl.eq_principle.strict_eq──▶ validators agree on WHAT to fetch
        │
        ▼
gl.nondet.web.render per URL, inside the nondet block
        │  capped at MAX_EVIDENCE_BODY_CHARS, fenced, labelled untrusted
        ▼
prompt: criteria by index + closed flag vocabulary + strict JSON output
        │
        ▼
normalisation: clamp score, bound indices, dedupe, derive level if absent
        │
        ▼
tiered validator (see CONSENSUS.md) ──▶ append ruling JSON
```

Unreachable sources do not silently vanish: they surface as `EVIDENCE_UNREACHABLE`, and a
case with nothing verifiable resolves to `INSUFFICIENT_EVIDENCE`.

## Prompt-injection posture

Rendered pages are attacker-controlled. Mitigations, in order of importance:

1. The URL set is fixed and agreed **before** any fetch, so injected content cannot cause
   new fetches.
2. Bodies are wrapped in explicit fences and labelled untrusted data that may contain
   instructions to ignore.
3. Output is constrained to indices and a bounded score, so a successful injection can move
   a number inside a band, not invent flags or criteria.
4. Every index is re-bounded in `_normalize_ruling` after the model returns.

## Reuse boundary

`_run_round`, `_render_evidence`, `_build_prompt` and `_normalize_ruling` touch only plain
strings, ints and lists. Swap the storage layer and the consensus core moves to another
contract unchanged.
