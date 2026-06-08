# Demo 01 — Look-through beneficial ownership of an operating company

## Story

You are running due diligence on **Acme Robotics Inc** (`OPCO`), a US operating
company. The cap table only shows two *direct* holders:

- `MIDCO` — Northgate Capital Sarl (Luxembourg) — 75%
- `MINOR` — Bluewater Ventures LP (Cayman fund) — 25%

Neither is a natural person. The question every AML / KYC / sanctions analyst
actually needs answered is: **who are the ultimate beneficial owners (UBOs),
and does anyone cross the 25% control threshold once you look through the
holding chain?**

The chain in `ownership.json`:

```
JANE (person) --100%--> TRUSTX (trust) --80%--> HOLDCO --90%--> MIDCO --75%--> OPCO
RAVI (person) --20%--> HOLDCO
RAVI (person) --10%--> MIDCO
MINOR (fund)  --25%--> OPCO
```

## Run it

Resolve the ultimate beneficial owners of `OPCO`, persons only:

```sh
python -m corpmap --format table owners demos/01-basic/ownership.json OPCO --persons-only
```

Expected effective ownership of OPCO:

- **Jane** = 100% x 80% x 90% x 75% = **54.0%**  -> MAJORITY / CONTROL / DISCLOSABLE
- **Ravi** = (20% x 90% x 75%) + (10% x 75%) = 13.5% + 7.5% = **21.0%** -> DISCLOSABLE

Full owner roll-up (including intermediate entities) as JSON:

```sh
python -m corpmap --format json owners demos/01-basic/ownership.json OPCO
```

Inspect just the direct cap table of any entity:

```sh
python -m corpmap entity demos/01-basic/ownership.json OPCO
```

Scan the whole structure for circular cross-holdings:

```sh
python -m corpmap cycles demos/01-basic/ownership.json
```

(This clean dataset has none; feed it a structure where two companies own each
other and `cycles` will report the loop.)

## Exit codes

`0` success, `2` on input/usage error (malformed dataset, unknown entity).
