# Load Matching Agent

## What it does

Given a load (a shipment that needs to move from A to B), this agent looks
at every available truck and driver and ranks the best 10 matches. It does
this with plain deterministic math — no AI model calls — so the same
inputs always produce the same ranking, and every score can be explained.

Each candidate truck is scored out of 100 points across four factors:

| Factor            | Points | What it measures |
|--------------------|--------|-------------------|
| Lane fit           | 0–40   | Is the truck already near the load's pickup city? Score drops the farther away (deadhead) the truck is. |
| Rate quality       | 0–30   | Does this load pay at or above what similar loads on this lane have paid recently? |
| HOS compliance     | 0–20   | Does the driver legally have enough hours-of-service left today (and room in their 8-day/70-hour cycle) to run this haul? |
| Equipment match    | 0–10   | Does the truck's trailer type (dry van / reefer / flatbed) match what the load needs, and — if the load is hazmat — does the driver hold a hazmat endorsement? |

**Trucks that can't legally or physically haul the load (wrong trailer
type, or a hazmat load with no hazmat-endorsed driver) are excluded from
the results entirely** — they aren't just scored low, they're left off the
list, the same way a dispatcher would never even consider them.

## Inputs

All data comes from fixture files in `/fixtures/load_matching/` — no live
data or external APIs are used in v1:

- `loads.json` — 15 sample loads (origin, destination, equipment type, rate, weight, pickup date, hazmat flag)
- `trucks.json` — 10 sample trucks (current city, equipment type, availability date, driver)
- `driver_hos.json` — hours-of-service data for each driver (hours driven/available today, last rest, 8-day cycle usage)

## Outputs

A ranked table (printed to the terminal) of up to 10 trucks for the
requested load, each with:

- Rank and total score (0–100)
- The four sub-scores (lane fit, rate quality, HOS, equipment)
- A one-line plain-English reason for the score

## How to run it

From the repository root, with the virtual environment active:

```bash
source .venv/bin/activate
python -m agents.load_matching.agent --load-id LOAD001
```

Add `--dry-run` to skip any future LLM-based steps and only show the
deterministic rule-based ranking (this agent doesn't call an LLM yet, so
today the two modes produce identical output):

```bash
python -m agents.load_matching.agent --load-id LOAD001 --dry-run
```

Load IDs available in the sample data are `LOAD001` through `LOAD015` —
see `fixtures/load_matching/loads.json` for the full list.

## How to run the tests

```bash
source .venv/bin/activate
python -m pytest agents/load_matching -v
```

This runs `evals.py`, which covers every scoring function individually
(including edge cases like an hours-exhausted driver, a hazmat load with
no endorsed truck, and a load priced clearly below its lane's average
rate) plus end-to-end checks that the top match for several sample loads
is stable and deterministic.
