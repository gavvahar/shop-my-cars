# Shop My Cars

An AI car-buying research agent. Tell it your budget and preferences, and it researches real options — both a local historical dataset and live web pricing — compiles a justified, cited comparison, and hands off to you for the final decision.

It **never** contacts a seller, submits a form, states a spec that isn't sourced from real data, or makes the purchase decision for you. Two separate human-approval checkpoints stand between research and any durable action.

Built for the "Mastering Agentic AI" bootcamp's Week 3 assignment: a real agentic system using LangGraph, not a one-shot LLM call or a simple retrieve-then-generate pipeline.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tools](#tools)
- [Persistence](#persistence)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup & Running](#setup--running)
- [API Reference](#api-reference)
- [Error Handling & Resilience](#error-handling--resilience)
- [Hard Limits & Safety Design](#hard-limits--safety-design)
- [UI](#ui)
- [Evaluation](#evaluation)
- [Known Limitations](#known-limitations)
- [Development](#development)

## Overview

Manually shopping for a car means cross-referencing spec sheets, historical pricing data, and current listings by hand across multiple tabs. This agent automates that research loop:

1. **Understand what you want** — extracts budget, vehicle style, fuel type, and other preferences from a plain-English message.
2. **Confirm before searching** — shows you what it understood and lets you correct it before spending time on research.
3. **Research from real sources** — filters a historical dataset, then searches the live web for current pricing on the top candidates.
4. **Compile a justified comparison** — a cited, qualitative comparison of the best matches, with every numeric spec (MSRP, MPG, horsepower) populated directly from the dataset in code, never restated by the LLM.
5. **Review before anything is saved** — you approve, ask for changes, or choose to save the shortlist, with a second explicit confirmation before any write actually happens.

## Architecture

Built as a LangGraph agent (`Python/backend/agent/graph.py`), served through a FastAPI + Jinja2 + vanilla JS chat UI (`Python/backend/main.py`, `POST /api/agent`). State is a plain `TypedDict` (`GraphState`) carrying the buyer's message, extracted requirements, dataset/web results, the compiled comparison, and routing/refinement fields between nodes.

**Flow:**

```
gather_requirements
      │
      ▼
[interrupt: confirm_requirements]  (approve / refine)
      │ approve                      │ refine (loops back up)
      ▼
search_dataset ──▶ search_web ──▶ compile_comparison
      │ (empty even after one
      │  relaxed retry)
      ▼
   no_results ──▶ END
      │
      ▼ (results found)
[interrupt: human_review]  (approve / refine / save)
      │ save                          │ refine (loops back to gather_requirements)
      ▼
[interrupt: confirm_save]  (confirm / decline)
      │ confirm
      ▼
save_shortlist ──▶ finalize_handoff
```

**Nodes:**

| Node                                 | Purpose                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `gather_requirements`                | Extracts `max_price`, `vehicle_style`, `fuel_type`, and freeform `must_haves` from the buyer's message via a structured-output LLM call. `validate_requirements` then cross-checks extracted `vehicle_style`/`fuel_type` against the dataset's real distinct values, demoting anything that doesn't genuinely match (including a small denylist for known-ambiguous tokens like `"gas"`, which would otherwise substring-match `"natural gas"`) into `must_haves` instead of silently applying a wrong filter.                                                       |
| `confirm_requirements` _(interrupt)_ | Pauses for the buyer to approve or refine the extracted requirements before any search happens.                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `search_dataset`                     | Structured Postgres filter (see [Tools](#tools)). Relaxes one filter and retries once if the initial query returns nothing, routing to `no_results` with an honest explanation if even that comes up empty.                                                                                                                                                                                                                                                                                                                                                          |
| `search_web`                         | Live web search for current pricing on the top 3 dataset candidates. Retries each query once on failure and degrades gracefully (a "live pricing unavailable" note) rather than failing the whole turn.                                                                                                                                                                                                                                                                                                                                                              |
| `compile_comparison`                 | An LLM call compiles qualitative pros/cons and source citations for the top candidates — explicitly instructed **not** to restate numeric specs. `validate_comparison` then strips any claim that mentions a spec unit anyway, any dollar figure that doesn't match a real MSRP/web price, and any source that isn't the literal word "dataset" or a URL that genuinely appears in the web results. `apply_authoritative_specs` populates `msrp`/`highway_mpg`/`city_mpg`/`horsepower` directly from the matched dataset row — these fields are never LLM-generated. |
| `human_review` _(interrupt)_         | Pauses with the full comparison for the buyer to approve, ask for changes, or choose to save it.                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `confirm_save` _(interrupt)_         | A second, separate confirmation specifically for the write — shown only if the buyer chose "save" at `human_review`.                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `save_shortlist`                     | The only write in the whole system (see [Tools](#tools)).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `finalize_handoff`                   | Produces the final summary message and ends the run.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |

## Tools

- **`search_dataset`** (READ) — `Python/backend/tools.py`. Structured filter (`max_price`, `vehicle_style`, `fuel_type`) over this app's own local car-specs Postgres dataset (seeded from the same source CSV used by this project's sibling repos, but its own independent database — no runtime dependency on those repos). Partial `ILIKE` matching (dataset values are compound strings like `"4dr SUV"`), cheapest-first ordering.
- **`search_web`** (READ) — live web search via `ddgs` (DuckDuckGo, zero signup/API key) for current market pricing, since the dataset only has historical MSRP.
- **`save_shortlist`** (WRITE) — `Python/backend/shortlists.py`. The only write action anywhere in this system. Persists to a local SQLite file (`shortlists.db`), gated behind its own `confirm_save` interrupt in addition to `human_review`. Deliberately a plain function, not an LLM-callable `@tool` — it should never be something the model decides to invoke on its own, only deterministic graph routing after an explicit human confirmation.

## Persistence

A SQLite-backed LangGraph checkpointer (`checkpoints.db`, `Python/backend/agent/graph.py`'s `open_checkpointer()`), keyed by a client-generated `thread_id`, so a research conversation survives a server restart, not just an in-process session — proven with a real test that closes one connection/graph instance and resumes from a genuinely separate one. Uses an explicit `allowed_msgpack_modules` allow-list for the Pydantic state types (`BuyerRequirements`, `CarComparison`), avoiding a LangGraph deserialization fallback path that's slated to be blocked in a future library version.

This is a distinct concept from `save_shortlist`'s `shortlists.db` — the checkpointer resumes an in-progress _conversation_, while a saved shortlist is the buyer's own explicit output.

## Tech Stack

- **Agent**: [LangGraph](https://langchain-ai.github.io/langgraph/) + [LangChain](https://python.langchain.com/) (`langgraph`, `langchain-core`, `langchain-ollama`, `langgraph-checkpoint-sqlite`)
- **Model**: self-hosted [Ollama](https://ollama.com/) (`qwen2.5:7b` by default), configured via `OLLAMA_BASE_URL`
- **Web**: FastAPI + Jinja2 + vanilla JS (no frontend framework/build step)
- **Database**: PostgreSQL (`psycopg[binary]`, `psycopg-pool`), self-contained — its own `postgres` service in `compose.yml`, seeded from a local CSV
- **Web search**: `ddgs`
- **Local persistence**: SQLite (both the checkpointer and saved shortlists)
- **Dev tooling**: `tox`, `ruff` (lint + format), `prettier`, `textlint`, TruffleHog (secret detection)

## Project Structure

```
shop-my-cars/
├── Python/
│   ├── backend/
│   │   ├── agent/
│   │   │   ├── graph.py          # LangGraph StateGraph, nodes, checkpointer
│   │   │   ├── requirements.py   # gather_requirements + validate_requirements
│   │   │   └── comparison.py     # compile_comparison + validate_comparison + spec authority
│   │   ├── static/
│   │   │   ├── css/style.css     # theme tokens + full page styling
│   │   │   └── js/
│   │   │       ├── chat.js       # chat UI logic, /api/agent client
│   │   │       └── theme.js      # light/dark/system toggle
│   │   ├── templates/index.html  # single-page chat UI
│   │   ├── db.py                 # Postgres queries (car dataset)
│   │   ├── db_config.py          # connection pool setup
│   │   ├── main.py                # FastAPI app, /api/agent, /health
│   │   ├── shortlists.py         # save_shortlist + SQLite storage
│   │   └── tools.py              # search_dataset, search_web
│   └── scripts/                  # spike/verification scripts, no mocks — run against real Postgres/Ollama
├── docs/eval.md                  # full eval results
├── compose.yml                   # standalone Docker Compose service
├── Dockerfile
├── requirements.txt
├── .env.example
└── pyproject.toml                # tox/ruff/prettier config
```

## Setup & Running

**Requires:** Docker, a reachable Ollama instance. This app is fully standalone — it runs its own Postgres (seeded from a local CSV) and doesn't depend on any other project's database or network.

| Variable                                              | Used by                             | Notes                                                                                                   |
| ----------------------------------------------------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Both                                | Yours to choose — this is this app's own database, not shared with anything else                        |
| `POSTGRES_HOST` / `POSTGRES_PORT`                     | Local (non-Docker) script runs only | `compose.yml` overrides both to the internal `postgres` service address for the containerized path      |
| `OLLAMA_BASE_URL`                                     | Both                                | Needs a reachable Ollama instance                                                                       |
| `AGENT_TIMEOUT_SECONDS`                               | Containerized app only              | Optional, defaults to `360` — how long `/api/agent` waits on a single graph turn before returning a 504 |

**Steps:**

1. Copy `.env.example` to `.env` and fill in real values.
2. Place the source dataset at `data/cars.csv` (gitignored, not committed — the "Car Features and MSRP" dataset, same one used by this project's sibling repos).
3. `docker compose up postgres -d`, then `docker compose --profile seed run seed` — creates the schema and loads the dataset. **Required once before first real use**; there's no automatic seed-on-startup.
4. `docker compose up --build` — builds from the repo's `Dockerfile` and runs the app on **port 8000**.
5. Open `http://localhost:8000` in a browser and start a conversation.

For local iteration without Docker, the `Python/scripts/spike_*.py` scripts exercise individual pieces (dataset search, web search, tool-calling reliability, the full graph including both interrupts and the save/persistence paths) directly against a real Postgres/Ollama instance — useful for debugging one layer without the HTTP/UI round-trip.

## API Reference

### `GET /health`

Returns `{"status": "ok"}`. Does not touch Postgres or Ollama — a fast liveness check only.

### `GET /`

Renders the chat UI (`templates/index.html`).

### `POST /api/agent`

Drives the graph — both fresh turns and resuming past an interrupt.

**Request body:**

```json
{
  "thread_id": "client-generated-uuid",
  "message": "I need a budget SUV under $25k"
}
```

or, to resume a paused interrupt:

```json
{
  "thread_id": "same-uuid-as-before",
  "resume": { "action": "approve" }
}
```

`resume.action` is one of `approve`, `refine` (with an additional `refinement` string), `save`, `confirm`, or `decline`, depending on which interrupt is currently pending.

**Response — paused at an interrupt:**

```json
{
  "status": "interrupted",
  "interrupt": {
    "type": "confirm_requirements",
    "requirements": { "...": "..." }
  }
}
```

**Response — turn complete:**

```json
{ "status": "done", "summary": "Research complete — 2 car(s) compared..." }
```

**Response — a request for this `thread_id` is already in flight:**

```json
{ "status": "busy", "detail": "Still working on your previous request..." }
```

## Error Handling & Resilience

- **In-flight request tracking**: `/api/agent` tracks which `thread_id`s currently have a graph invocation running. A second request for the same `thread_id` while one is still in flight gets an immediate `"busy"` response instead of racing a second concurrent invocation against the same checkpointed state. The lock is released only when the underlying invocation actually finishes — not when an HTTP request times out waiting on it — since the invocation itself keeps running in the background regardless.
- **`search_dataset` empty results**: relaxes one filter (`fuel_type` first, then `vehicle_style` — never `max_price`, the buyer's actual budget) and retries once before concluding nothing matches.
- **`search_web` failures**: retries each per-car query once, then degrades to a "live pricing unavailable" note rather than failing the whole turn. `ddgs` rate limits have been the most common real failure mode encountered during development.
- **Request timeout**: bounded by `AGENT_TIMEOUT_SECONDS` (default 360s) — a single graph turn (especially `compile_comparison`'s LLM call) can genuinely take several minutes on CPU-only inference, particularly under concurrent load.

## Hard Limits & Safety Design

- Never contacts a seller or submits any external form.
- Never states a car spec that isn't sourced from the real dataset or a real web result — enforced in code (`validate_comparison`, `apply_authoritative_specs`), not just prompted for.
- Two separate human-in-the-loop confirmations stand between any research and any durable write: `human_review` (approve the comparison) and `confirm_save` (confirm the actual save).
- Historical dataset MSRP is never presented as current market pricing without a live web result backing it — degrades to an explicit "live pricing unavailable" note rather than mislabeling stale data as current.

## UI

A single-page chat interface (no frontend framework) with:

- **Light / Dark / System theme toggle**, persisted via `localStorage`, with an anti-flash inline script so the correct theme applies before first paint.
- **A typing indicator** shown for the duration of every in-flight request — turns can take anywhere from a few seconds to several minutes, so this distinguishes "still working" from "broken."
- **Pending-action panel** rendering each interrupt type (confirm requirements, review comparison, confirm save) with its own action buttons, which disable while a request is in flight to prevent double-submits.

## Evaluation

See [`docs/eval.md`](docs/eval.md) for the full 10-question eval, run live against the running app (not scripted shortcuts) — questions, actual observed outcomes, and pass/fail against the "zero fabricated specs" bar. Two real bugs were found and fixed directly from that eval run (a citation-validation gap and a requirements-extraction substring-match bug); both are detailed there.

## Known Limitations

Full detail in `docs/eval.md`'s Known Limitations section — summarized here:

- **Cross-car URL misattribution**: a cited web source URL is real, but in rare cases may have been returned for a different candidate car's search query rather than the one it's attached to (results are matched globally, not per-candidate). Deferred as lower-severity than the fabrication classes already fixed.
- **Free-text qualitative claims**: numeric specs (MSRP, MPG, HP) are code-populated from the dataset and can't be wrong; free-text pros/cons prose still relies on prompt instructions plus a regex backstop, not a full guarantee.
- **Ollama runs on CPU** (not GPU) — concurrent requests compete for the same cycles rather than parallelizing, so latency can spike well past the typical turn time under concurrent load.

## Development

```bash
tox -e all
```

Runs the full check suite: `ruff` lint + format check, `no_classes_check.py` (this repo bans `class` statements outside a small exclude list for Pydantic models), `combined_imports_check.py`, `prettier`, `textlint`, `taplo` (TOML), and a TruffleHog secret-detection scan. The secret-detection env needs the `docker` CLI on the host running it — it will fail with a "no such file" error if run inside a nested container without Docker-in-Docker; run it directly on the host in that case.
