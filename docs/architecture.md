# Architecture Overview

## What this platform is

This is a set of small, focused software "agents" that each automate one
task a freight brokerage does every day. In v1 there are five planned
agents — Load Matching, Document Extraction, Exception Detection, Rate
Negotiation, and Invoice Audit — but only **Load Matching** is built so
far. Each agent is independent: it can be built, tested, and sold on its
own, and later they'll share data through a common orchestration layer.

## How a request flows through the system

A user (a dispatcher, in the Load Matching case) runs an agent from the
command line with a specific input — for example, "find trucks for load
LOAD001." The agent pulls the relevant data (loads, trucks, driver hours),
runs it through a set of scoring rules, and prints a ranked, explained
result. Nothing here calls the internet or a live database yet: all data
in v1 comes from realistic fixture files so the whole system can be built,
tested, and demoed without depending on a customer's real systems.

## Why deterministic logic comes first

Every agent is built with a strict separation: **rules.py holds pure,
deterministic scoring functions with no AI involved**, while an LLM (via
`shared/llm_client.py`) is reserved for tasks that genuinely need language
understanding — reading a messy PDF, negotiating tone, summarizing an
exception. Load Matching, for instance, needs no AI at all: "is this truck
near this load, priced well, legally able to drive it, and the right
trailer type" is just arithmetic. Keeping deterministic logic first makes
the system cheaper to run, instant to test, and — critically — auditable:
a dispatcher can see exactly why a truck scored what it scored.

## The shared foundation

Every agent is built on five shared modules so behavior is consistent
across the platform: `config.py` loads settings and secrets from the
environment; `errors.py` defines one exception hierarchy every agent
raises into; `logging.py` writes structured JSON logs so every action is
traceable after the fact; `llm_client.py` is the single door through which
any Claude API call must pass, so retries, cost logging, and schema
validation happen in exactly one place; and `fixtures.py` loads the fake
but realistic test data every agent uses in place of live systems in v1.

## Load Matching Agent, concretely

Given a load, the agent scores every available truck out of 100 points
across four factors — lane fit (is the truck nearby), rate quality (does
this load pay well for its lane), HOS compliance (does the driver legally
have the hours), and equipment match (right trailer, right endorsements).
Trucks that are legally or physically incompatible (wrong trailer type, or
a hazmat load with no hazmat-endorsed driver) are excluded outright rather
than merely down-scored. The result is a ranked, explained shortlist a
dispatcher can act on immediately.

## What's next

Document Extraction, Exception Detection, Rate Negotiation, and Invoice
Audit will follow the same pattern: fixtures first, deterministic rules
where possible, LLM calls only where genuinely needed, and a human review
queue for anything the system isn't confident about. An orchestration
layer will eventually tie the five agents together into one workflow.
