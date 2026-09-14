# Freight Agent Platform

A multi-agent platform for freight brokerages and carriers: Load Matching,
Document Extraction, Exception Detection, Rate Negotiation, and Invoice
Audit. See `CLAUDE.md` for the full architecture and build order, and
`docs/architecture.md` for a plain-English overview.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
```

## Agents

- `agents/load_matching/` — ranks trucks against loads (v1, complete — see its README.md)
- `agents/document_extraction/` — not yet built
- `agents/exception/` — not yet built
- `agents/rate_negotiation/` — not yet built
- `agents/invoice_audit/` — not yet built
