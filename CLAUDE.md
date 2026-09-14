# FREIGHT AGENT PLATFORM — MASTER ARCHITECTURE

## PROJECT PURPOSE
A multi-agent platform for freight brokerages and carriers. Five agents: Load Matching, Document Extraction, Exception Detection, Rate Negotiation, Invoice Audit. Sold as SaaS to small/mid freight companies.

## NON-CODER OPERATOR
The operator is not a developer. Every response must:
- Give exact terminal commands to run
- State expected output before running
- Explain errors in plain English when they occur
- Never assume knowledge of git, Python, or file paths
- Ask for confirmation after each numbered step before moving on

## TECH STACK (LOCKED — DO NOT CHANGE)
- Python 3.11+
- Pydantic v2 for all schemas
- Anthropic SDK (claude-sonnet-4-5) for LLM calls
- SQLite for v1 persistence (upgrade to Postgres later)
- pytest for all tests
- Rich for CLI output
- No async in v1 (keep it simple)
- No Docker in v1

## FOLDER STRUCTURE (LOCKED)
/freight-agents
  CLAUDE.md
  README.md
  requirements.txt
  .env.example
  .gitignore
  /agents
    /load_matching
    /document_extraction
    /exception
    /rate_negotiation
    /invoice_audit
  /shared
    llm_client.py      # single wrapper for all Anthropic calls
    logging.py         # structured logging
    config.py          # env var loading
    errors.py          # custom exceptions
    fixtures.py        # shared fixture loaders
  /fixtures            # all fake test data
  /logs                # runtime logs (gitignored)
  /data                # sqlite db, state files (gitignored)
  /evals               # cross-agent eval harness
  /docs                # architecture, pricing, customer notes

## EVERY AGENT FOLLOWS THIS STRUCTURE
/agents/<agent_name>/
  __init__.py
  agent.py          # main entry point + CLI
  schemas.py        # Pydantic models
  tools.py          # data access functions
  rules.py          # deterministic logic (where applicable)
  evals.py          # pytest test cases
  README.md         # plain-English explanation
  fixtures/         # agent-specific fixtures (if needed)

## CODING RULES
- Every function has a docstring
- Every public function has at least one pytest test
- Type hints on all function signatures
- No print() — use the shared logger
- No hardcoded API keys — always os.getenv()
- No real API calls in tests — use fixtures/mocks
- All LLM calls go through shared/llm_client.py
- All exceptions inherit from shared/errors.py

## AGENT DESIGN PRINCIPLES
- Deterministic logic FIRST, LLM only when needed
- LLM outputs must be structured JSON, validated by Pydantic
- Every LLM call logs prompt + response + cost estimate
- Every agent has a --dry-run flag
- Every agent that produces output for humans has a confidence score
- Confidence < 0.80 → route to human review queue
- No agent sends email/messages autonomously in v1 — human approves

## SHARED MODULES (BUILD FIRST, ONCE)
### shared/config.py
Loads from .env: ANTHROPIC_API_KEY, DATABASE_PATH, LOG_LEVEL, FIXTURES_PATH

### shared/llm_client.py
- call_claude(prompt, system, schema=None, model="claude-sonnet-4-5") -> dict
- Logs every call: timestamp, model, tokens_in, tokens_out, cost_estimate
- Retries 2x on failure with exponential backoff
- Validates JSON response against provided Pydantic schema
- Raises LLMError on validation failure

### shared/logging.py
- get_logger(name) -> Logger
- Structured JSON logs to /logs/<name>.log
- Also prints to console in dev

### shared/errors.py
- AgentError (base)
- LLMError
- DataError
- ValidationError
- HumanReviewRequired

### shared/fixtures.py
- load_json(path) -> dict
- load_fixtures(agent_name, filename) -> list[dict]

## BUILD ORDER (LOCKED)
1. Shared modules + folder structure + requirements.txt
2. Load Matching Agent (reference implementation)
3. Document Extraction Agent
4. Exception Agent
5. Rate Negotiation Agent
6. Invoice Audit Agent
7. Orchestration layer

## SESSION PROTOCOL
At start of every session:
- Read this file
- State which agent we're working on
- State what step of that agent we're on

At end of every session:
- Run pytest on the agent we worked on
- Commit with message: "agent: <name> — <step description>"
- Summary in 3 sentences

## TOKEN DISCIPLINE
- One agent per session, fresh context
- Reference files by path, never re-paste
- Stop after each numbered step, wait for confirmation
- If stuck twice, suggest /compact before continuing

## EVAL REQUIREMENTS (PER AGENT)
Minimum test cases:
- Load Matching: 20
- Document Extraction: 15
- Exception: 20
- Rate Negotiation: 15
- Invoice Audit: 25

Each eval must include at least 3 edge cases and 1 "should fail gracefully" case.

## PRICING (FOR REFERENCE ONLY — NOT CODE)
- Load Matching: $20-40/truck/mo
- Document Extraction: $299/mo + $0.25-1/doc
- Exception: $25-50/truck/mo
- Rate Negotiation: 15-25% of rate improvement
- Invoice Audit: 20-30% of recovered $ (min $299/mo)
