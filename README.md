# Shop My Cars

An AI car-buying research agent. Tell it your budget and preferences, and it researches real options — both a local historical dataset and live web pricing — compiles a justified, cited comparison, and hands off to you for the final decision. It replaces manual spec-sheet/pricing cross-referencing; it never contacts a seller, submits a form, or decides for you.

## Architecture

Built as a LangGraph agent (`Python/backend/agent/graph.py`), served through a FastAPI + Jinja2 + vanilla JS chat UI (`Python/backend/main.py`, `POST /api/agent`).

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

**Tools:**

- `search_dataset` (READ) — structured filter over a local historical car-specs dataset (Postgres, shared with the `ask-my-cars` project's instance).
- `search_web` (READ) — live web search (DuckDuckGo via `ddgs`) for current market pricing, since the dataset only has historical MSRP.
- `save_shortlist` (WRITE) — the only write action in the whole system. Persists to a local SQLite file (`shortlists.db`), gated behind its own separate confirmation interrupt in addition to the `human_review` step.

**Persistence:** a SQLite-backed LangGraph checkpointer (`checkpoints.db`) keyed by a client-generated `thread_id`, so a research conversation survives a server restart, not just an in-process session.

**Model:** self-hosted Ollama (`qwen2.5:7b` by default), configured via `OLLAMA_BASE_URL`.

## Setup & Running

Requires: a reachable Postgres instance with the car-specs dataset (shared with `ask-my-cars`, running on the same host), a reachable Ollama instance, Docker. This app is standalone — it doesn't join `ask-my-cars`' Docker network or depend on how that project runs, only that its Postgres is reachable on the host.

1. Copy `.env.example` to `.env` and fill in `POSTGRES_DB`/`POSTGRES_USER`/`POSTGRES_PASSWORD` (`OLLAMA_BASE_URL` already has a working default; `POSTGRES_HOST`/`POSTGRES_PORT` are only used for local, non-Docker script runs — `compose.yml` itself overrides `POSTGRES_HOST` to `host.docker.internal` for the containerized path).
2. `docker compose up --build` — builds from the repo's `Dockerfile` and runs the app on **port 8000** (see `compose.yml`). This app deliberately does **not** run its own Postgres container; it connects to the existing `ask-my-cars` instance as a client, reachable on the host via `host.docker.internal`.
3. Open `http://localhost:8000` in a browser and start a conversation.

For local iteration without Docker Compose, the various `Python/scripts/spike_*.py` scripts exercise individual pieces (dataset search, web search, the full graph including both interrupts and the save path) directly against a real Postgres/Ollama instance — useful for debugging a specific layer without the HTTP/UI round-trip.

## Hard Limits

- Never contacts a seller or submits any external form.
- Never states a car spec that isn't sourced from the real dataset or a real web result — enforced in code (`validate_comparison`, `apply_authoritative_specs` in `comparison.py`), not just prompted for.
- Two separate human-in-the-loop confirmations stand between any research and any durable write: `human_review` (approve the comparison) and `confirm_save` (confirm the actual save).
- Historical dataset MSRP is never presented as current market pricing without a live web result backing it — degrades to an explicit "live pricing unavailable" note rather than mislabeling stale data as current.

## Evaluation

See [`docs/eval.md`](docs/eval.md) for the full 10-question eval, run against the live app — questions, actual observed outcomes, and pass/fail against the project's zero-fabricated-specs bar.

## Known Limitations

Full detail in `docs/eval.md`'s Known Limitations section — summarized here:

- **Cross-car URL misattribution**: a cited web source URL is real, but in rare cases may have been returned for a different candidate car's search query rather than the one it's attached to (results are matched globally, not per-candidate). Deferred as lower-severity than the fabrication classes already fixed.
- **Free-text qualitative claims**: numeric specs (MSRP, MPG, HP) are code-populated from the dataset and can't be wrong; free-text pros/cons prose still relies on prompt instructions plus a regex backstop, not a full guarantee.
- **Ollama runs on CPU** (not GPU) — concurrent requests compete for the same cycles rather than parallelizing, so latency can spike well past the typical ~4-minute turn under concurrent load. See `docs/eval.md` for the specifics observed during the real eval run.
