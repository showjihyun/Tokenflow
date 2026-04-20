# TODOS

Deferred work items captured during planning/reviews. Each entry should have enough
context that someone picking it up in 3 months understands the motivation and where
to start.

---

## Observability: propagate correlation ID into background tasks
**Added:** 2026-04-20 (plan-eng-review, v1.1 roadmap)

**What:** Extend request-scope correlation ID (planned in v1.1 JSON logging) to run
inside the TranscriptTailer poll loop, the EventTailer ingest loop, and the hourly
waste `sweep`. Each loop tick should allocate a task_id and bind it to the logging
contextvar for the duration of the tick.

**Why:** v1.1 request-scope ID lets us trace an HTTP request end-to-end, but the
most expensive failures (long-running tailer stalls, waste sweep hangs) happen
outside of request scope. Without a task_id, those log lines only carry
`logger.name` for grouping, which hides per-tick duration and per-loop failure
rates.

**Pros:** Full observability — every log line attributable to a specific tick or
sweep. Enables cross-tick timing analysis.

**Cons:** ~10 call sites to wire (every bg loop entrypoint). Modest test surface
(contextvar propagation across `asyncio.run_in_executor` + thread pool).

**Context:** v1.1 chose request-scope-only to keep the first pass small.
`adapters/web/middleware/request_id.py` will be the template; the tailer loops
sit in `adapters/transcript/tailer.py` and `adapters/hook/event_tailer.py`;
`waste_sweep()` lives in `use_cases/detect_waste.py`.

**Depends on:** v1.1 JSON logging landed.

---

## CI: coverage fail-on-regression gate
**Added:** 2026-04-20 (plan-eng-review, v1.1 roadmap)

**What:** Once the v1.1 coverage baseline is captured in CI artifacts, add a
PR-blocking check that fails when a PR's coverage drops below baseline (or below
a fixed 70% line threshold, whichever is higher).

**Why:** v1.1 reports coverage but does not gate on it. Human review of coverage
diffs is unreliable over time — drift happens silently. A soft gate in CI forces
the author to either add tests or justify the regression.

**Pros:** Prevents coverage decay. No external service needed (use artifact +
`diff-cover` or a small Python script comparing current vs baseline JSON).

**Cons:** Flaky if baseline shifts with unrelated changes (mitigation: use branch
HEAD of `main` as baseline, not a fixed file). Some legitimate low-test-value
changes (docs-only edits, markdown, etc.) may need a skip label.

**Context:** Add in the CI workflow after `pytest --cov` / `vitest --coverage`
run. Compare `coverage.xml` totals against `git fetch origin main && git show
origin/main:coverage-baseline.xml` or equivalent.

**Depends on:** v1.1 CI coverage reporting landed.

---

## Logging perf: QueueHandler for async-safe log pipe
**Added:** 2026-04-20 (plan-eng-review, v1.1 roadmap)

**What:** Replace the synchronous `RotatingFileHandler` / `TimedRotatingFileHandler`
in v1.1 with `logging.handlers.QueueHandler` + a `QueueListener` running on its
own thread. File I/O happens off the asyncio event loop.

**Why:** Python's `logging` uses a module-global lock, and the default file
handlers do synchronous I/O. In practice this is fine for a local single-user
app, but waste sweep can burst hundreds of log lines at once — and while we
haven't measured it, this is the classic async footgun to watch for.

**Pros:** Eliminates event-loop jitter on log bursts. Standard library — no new
dep. Minimal code change (wrap existing handler in queue pair at setup time).

**Cons:** Adds a background thread. Log ordering guarantees weaken slightly
(queue may deliver out of strict arrival order under stress — negligible in
practice). Graceful shutdown needs `QueueListener.stop()` in the serve
teardown path.

**Context:** Trigger for promoting this: measured jitter on `/api/kpi/summary`
p99 when a sweep is running, or user reports. Until then, YAGNI.

**Depends on:** v1.1 JSON logging landed. Measurement infrastructure (could
just be manual `ab` / `hey` benchmark during sweep).
