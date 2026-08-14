# Examples

Each file holds the constructor argument and an `open_case` payload for one due-diligence
shape. They are plain JSON so they can be fed to Studio, `scripts/run_case.py`, or any
client.

| File | Shape |
| --- | --- |
| `vendor_onboarding.json` | Prepayment to a first-time supplier. Tests operational evidence and trading history. |
| `otc_desk_kyb.json` | Large, fast settlement against a thin footprint. Should land on `INSUFFICIENT_EVIDENCE`, not `LOW`. |

## Using one

```sh
python scripts/deploy.py   --allowlist examples/vendor_onboarding.json
python scripts/run_case.py --address 0xYourContract --case examples/vendor_onboarding.json
```

In Studio, paste the `constructor.allowed_domains` string as the single constructor argument,
then copy the six `open_case` fields into the method form in order.

## Writing good criteria

- **Be checkable.** "Registered legal entity verifiable in a public registry" beats
  "legitimate company".
- **One claim per criterion.** Rulings return *indices*; a compound criterion cannot be
  half-unmet.
- **Never reorder after a case is open.** Indices in stored rulings point into this array.
- **Put the stakes in `context`, not in the criteria.** A USD 500 sample order and a USD 5M
  facility are the same criteria at different thresholds, and the model is told the context.
