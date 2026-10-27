# Feedback — Reflex (Physical AI track)

**Built with:** `nvidia/Nemotron-3-Ultra-550b-a55b` (planner, `settings.model_ultra`),
`nvidia/nemotron-3-super-120b-a12b`, `nvidia/nemotron-3-nano` and `nvidia/cosmos-reason-2`
(pinned for tiering and vision; declared in `GET /v1/envelope/info`, **not yet called**) ·
Token Factory via the **OpenAI-compatible** endpoint `https://api.tokenfactory.nebius.com/v1/` ·
Token Factory **Sandboxes**: planned and specified, not executed (`TODO_VERIFY(sandbox-sdk)`) ·
Nebius **AI Cloud Serverless Jobs**: planned, not submitted.
**Where:** Amstelveen, Netherlands (Europe/Amsterdam) · **When:** 2026-10-24 → 2026-10-30 · **Spend:** **$0 across 0 calls**
**Repo:** <https://github.com/knarayanareddy/reflex-physical-ai> · **Contact:** `@knarayanareddy`

> **Read this first, because it changes how you should weigh the rest.** This build made **zero** live
> Token Factory calls. `LIMITATIONS.md` says so in the row a reviewer checks first — *"Token Factory calls
> | **0.** No key in the build environment; no telemetry line exists"* — and `runs/ledger.jsonl` does not
> exist, so the claim is checkable rather than asserted. What follows is therefore **not** a workload
> report. It is the view from *before the first call*: the transport and telemetry we wrote against the
> documented surface, and the precise places where a physical-AI team's integration path stops. If you
> want the p50/p99 table a platform team actually wants, §4 states exactly which fields will fill it and
> from which file. A feedback document that reports those percentiles without a key is inventing them.

**Context.** Reflex is a deterministic veto layer for robot actions. A cloud planner proposes; a local,
network-free envelope (ten interlocks, V1–V10) decides whether the action ships, and every decision —
including the refusals — is written to an append-only ledger. Measured on 1,000 synthetic actions:
1,000 actions planned, 420 vetoes enforced, 248 prevented (170 contacts + 78 boundary excursions), 0
shipped. The interesting property for this document is that **the model is explicitly not in the safety
path**, which puts unusual pressure on the *shape* of the model's output and on the *provenance* of the
record — the two things §2 and §5 are about.

---

## 1. What worked, specifically — and why it mattered

- **The OpenAI-compatible surface removed an SDK from a safety-critical path.** `openai_completer`
  (`backend/app/plan/ultra.py:346-394`) is **48 lines** including its docstring: construct
  `OpenAI(base_url=..., api_key=..., timeout=60.0)`, call `client.chat.completions.create`, map the
  response. That is the whole vendor integration. For a project whose selling point is "a human can
  audit the refusing layer", every dependency in the proposal path is a liability, and being able to use
  the client every reviewer already knows — instead of a bespoke SDK — is worth real review time. This
  was the single decision that made the cloud half of the project feasible in four days.

- **Model IDs as configuration, not code.** The four catalogue IDs live in `backend/app/config.py:46-49`
  and are echoed by `GET /v1/envelope/info` (`backend/app/main.py:103-107`), so "which model planned
  this action" is a value an auditor can read out of the running system rather than a constant buried in
  a call site. For a tiered planner (ultra → super → nano) that is the difference between a cost story
  and a cost *claim*. `cost_usd`/`latency_ms` per call were designed into the ledger from the start for
  the same reason.

- **An OpenAI-shaped `usage` object is the right shape for a safety ledger.** `Completion` carries
  `prompt_tokens`, `completion_tokens`, `cached_tokens` and `latency_ms`
  (`ultra.py:75-80`), which is exactly the per-decision granularity an edge/cloud split needs: the
  ledger answers "what did this refusal cost to *propose*", not "what did the month cost".

## 2. Documentation gaps I hit

- **Structured output — the highest-impact gap for any project with a gate.**
  `docs.tokenfactory.nebius.com/ai-models-inference/json` is the page our platform notes name, and it was
  **not reachable from our build environment** (egress allowlist; `docs/DISCREPANCIES.md:74` records this
  as `TODO_VERIFY(plan-json-mode)`). So we cannot tell you whether
  `response_format={"type": "json_object"}` or a `json_schema` variant is accepted, per model or at all.
  What we wrote instead (`ultra.py:150-175`) is: parse the message text, strip a Markdown fence if
  present (`_strip_fence`), `json.loads`, then validate against our own JSON Schema and *abstain* on
  `schema_violation`. **That workaround is the load-bearing risk in the whole project** — it is exactly
  the "model prose becoming a verdict" failure mode a deterministic gate exists to prevent.
  **Suggested addition to that page:** one table — model × accepted `response_format` values × what
  happens on a schema miss (400 vs. silently-ignored) × whether `strict` is honoured. That page, filled
  in, would convert a hand-rolled parser into a validated call for every entrant building an evidence
  gate.

- **The cached-token field path is undocumented at the level that matters.** We read
  `usage.prompt_tokens_details.cached_tokens` through a defensive `getattr` chain, defaulting to `0`
  (`ultra.py:384-386`). If that path is not populated by your API, our cost ledger reports **cache
  savings of exactly zero** and looks correct doing it. A silent zero in a cost-control artefact is worse
  than an error, because nothing fails. **Request:** document the exact `usage` object per model, and
  state plainly whether "cached tokens not reported" means "no hits" or "not instrumented".

- **Sandbox SDK: no signature anywhere we could reach.** We declined to invent one — `sandbox_plan`
  (`backend/app/sandbox/replay_pack.py:300-330`) emits the plan, the intended network-off step and the
  exact offline verify command, and sets `sdk.status: TODO_VERIFY(sandbox-sdk)`. The result is an honest
  gap in the submission instead of a plausible-looking artefact that never ran. **Request:** one
  copy-pasteable example covering the whole arc — create from image UUID → run a command with the guest
  network disabled → download the produced bytes → delete — with the **exact kwarg names**. We needed
  precisely that and could not find it.

- **Is the guest network restricted per image, per operation, or per sandbox?** Our notes only say
  "where supported" (`docs/PLATFORM-CAPABILITIES.md` §3). Our strongest available claim is "this pack
  verifies with no network", and its strength depends entirely on that scope. If it is per-operation, we
  need to know it is assertable at the moment of the run; if per-image, it must be part of the image's
  identity for the claim to survive.

- **AI Cloud Job limits are unstated for a simulation lane.** We wanted to run 1,000 simulation replays
  as a Job (container size, GPU availability, and how GPU is requested, wall-time ceiling, and what
  happens to a Job that exceeds it). Without those numbers the lane stays designed-but-unsubmitted; with
  them it is a one-file change in `jobs/`.

## 3. Things that broke, or behaved surprisingly

- **Mine:** our telemetry ledger derived its path from `__file__`, which resolved to
  `site-packages/../runs` when installed as a package and to `/app/runs` in a container — i.e. it wrote
  audit telemetry *next to installed dependencies*. It is now an explicit `REFLEX_LEDGER_PATH` with an
  fsync'd, append-only, one-`write()`-per-line format and a per-line `id` for de-duplication
  (`backend/app/tf/ledger.py` header records the whole lesson). The confusing part was that **nothing
  failed**: the file appeared, it was just in the wrong place, and a cost record you cannot find is
  indistinguishable from a cost record you never wrote. This is the same silent-zero hazard as the cached
  tokens above, and it is why we now treat "where did the artefact land" as part of the contract.

- **Mine, and a documentation bug underneath it:** `openai_completer` catches every provider exception and
  re-raises one typed failure — `raise PlannerError(f"model call failed: {exc}") from exc`
  (`ultra.py:377-379`). That was deliberate (no raw provider error should escape into a safety path), but
  it collapses 401 / 429 / timeout / malformed-JSON into one string, and it discards any request or
  operation id in the response. Cost us debugging time and, more importantly, an auditable trail. **The
  genuinely useful question for your team:** which header carries a request id on the OpenAI-compatible
  endpoint, and is it guaranteed present on error responses? If you document that one header, every
  entrant with a "no silent failures" requirement can preserve it instead of squashing it.

- **Environmental, not yours:** the documentation hosts (`docs.tokenfactory.nebius.com`,
  `docs.nebius.com`) were unreachable from our build sandbox, so several integration decisions were made
  against the repo's own platform notes rather than the source of truth, and are marked `TODO_VERIFY` in
  `docs/DISCREPANCIES.md:74-81` rather than guessed. Worth knowing that "read the docs" was not available
  to us at build time.

## 4. Numbers you might want

Cloud rows are **NOT MEASURED** — 0 calls, no key, no `runs/ledger.jsonl`. They are listed so you can see
what the instrumentation would produce, not to imply a result.

| Metric | Value |
|---|---|
| Total spend | **$0 across 0 calls** (`LIMITATIONS.md`; no `runs/ledger.jsonl` exists) |
| Tokens (prompt / completion / cached) | **NOT MEASURED** → would land in `prompt_tokens`, `completion_tokens`, `cached_tokens` |
| Cost per 1,000 planned actions | **NOT MEASURED** → `cost_usd`, one line per decision |
| Latency p50 / p95, Amsterdam → endpoint | **NOT MEASURED** → `latency_ms`, measured around the call in `openai_completer` |
| Local envelope decision latency (the part that is on the robot) | **~120 µs** median in the recorded session (`latency_us` per decision; no network, no model) |
| Tiering delta (ultra vs super vs nano, same proposal) | **NOT MEASURED** — the three IDs are pinned, the comparison needs three calls |
| Sandbox image build / cold start / per-operation | **NOT MEASURED** — SDK call not written (`TODO_VERIFY(sandbox-sdk)`) |
| Replay artefact | **0.70 MiB** bundle, 100 decisions × 2 arms, verified **offline** (integrity + re-execution), 0 shipped collisions |
| Test suite | **431** (`make check`) — 430 plus one that requires the generated replay bundle, which is gitignored, so a fresh clone shows **430 passed, 1 skipped** |
| Failure rate by class | **NOT APPLICABLE** — no calls; the gate's own classes are `schema_violation`, `abstain`, `ALLOW`, `VETO` |

## 5. What I wished existed

- **Use case:** a robot on a factory floor makes 420 refusals a day, and the safety engineer needs to
  prove *after the fact* that each refusal happened on the device, unaltered, at a stated time. Our
  ledger has the decisions; what it does not have is a way to get them to a platform with an identity and
  an integrity story. **Workaround:** a local append-only JSONL plus an fsync'd path and a hash per
  record — durable, but the audit trail ends at the device. **Request:** a documented ingestion path for
  device-originated records — device identity, signed/attributable records, and explicit **offline
  buffer-and-backfill** semantics (what happens to a record produced during a 6-hour network partition is
  the actual question, and it is the one nobody documents). For a sponsor pushing physical AI this is the
  gap between "the cloud can plan" and "the cloud can be trusted with what the edge decided".

- **Use case:** my strongest safety claim is "this artefact verifies with the guest network disabled", and
  a reviewer should not have to take my word that it was disabled. **Workaround:** the plan lists
  `network: disabled` as a step attribute and the verifier refuses to fetch anything. **Request:** make
  the network policy a property **attested in the operation's result** (and, ideally, in the artifact
  metadata), so the claim is evidence rather than configuration.

- **Use case:** a per-call cost ledger should not need a hard-coded price table. Our
  `record_telemetry` defaults `cost_usd=0.0`, which means an unpriced call is recorded as **free** — the
  silent-zero failure again. **Request:** return a per-response cost or a priced usage object, or a
  documented `pricing` endpoint, so the number has one source of truth.

- **Use case:** reproducible evaluation — the same decision replayed under a pinned image. **Request:**
  document that an image UUID is immutable and content-addressed (and how to verify it), so "the same
  bytes ran" is a checkable statement rather than an assumption.

## 6. Non-English / international notes

We build in the Netherlands, and the two questions we could not answer from Amsterdam matter more for a
safety system than for a chat app. **(a) Latency budget.** Our design tolerates a slow cloud planner
precisely because the refusing layer is local; but the split we would like to publish is "plan in p50 X
ms from AMS, refuse in 120 µs on the device". The X is unmeasured here (0 calls), and it is the number a
European buyer asks for first. **(b) Residency.** A safety ledger is an industrial record; EU customers
will ask where it is stored and under which jurisdiction, and whether Sandboxes/Endpoints can be pinned to
an EU region per operation. Neither is answerable from the pages we could reach, so both are marked
`TODO_VERIFY` rather than assumed. A one-line statement of region availability on the Sandboxes and
Serverless overview pages would remove a whole category of support questions from EU entrants.

## 7. One thing I would tell a friend starting tomorrow

Use the OpenAI-compatible endpoint and bring your own client — that part is genuinely frictionless, and
48 lines is a fair price for a fully auditable model call. Then spend your first hour on the **response
shapes**, not the endpoints: which `usage` fields are actually populated, whether `response_format` is
honoured per model, and which header carries a request id. Everything downstream of a planner is a
parser, and the failure mode you will actually hit is not an error — it is a plausible zero. Validate
every field, emit your own ledger line, and treat "the docs didn't say" as a `TODO_VERIFY` you list in
your submission rather than a guess you ship.

---

**Thanks** — the deterministic-gate framing in the track's materials is what made this project take its
current shape: keep the model out of the refusal path and make the refusal auditable. That is a good
thesis to build a track around.

`knarayanareddy` · Reflex · Amstelveen, NL

---

## Preflight (self-check against `docs/templates/devpost-feedback.template.md`)

- [x] ≥400 words, ≥6 distinct points — 5 documentation gaps, 2 self-inflicted breakages, 4 feature requests
- [x] ≥4 points with a number, a doc URL or a code snippet — `ultra.py:346-394` (48 lines),
      `config.py:46-49`, `ultra.py:377-379`, `ultra.py:384-386`, 0.70 MiB / 100 decisions, 431 tests
- [x] ≥1 concrete feature request with a use case first — §5, four of them
- [x] ≥1 point where the fault was mine — §3, both entries, with what made them confusing
- [x] No invented measurements — the cloud rows in §4 say **NOT MEASURED** and name the field that will
      fill them
- [ ] **Doc URLs were not visited.** `docs.tokenfactory.nebius.com/...` was unreachable from the build
      environment; those references are reproduced from `docs/PLATFORM-CAPABILITIES.md` and are marked
      as such here rather than presented as pages I read. **Do not** paste this section into a form that
      requires verified URLs without checking each one.
- [ ] Contact detail: handle only. **TODO_VERIFY** if an email is wanted for follow-up.
- [x] Every number matches the README and the Devpost copy (1,000 / 420 / 248 / 0; 431)

---

*An earlier review of the Devpost submission form itself — six process observations, including the
criterion that asks for runtime Token Factory usage from a build with no key — is preserved in
`docs/DEVPOST_FORM_NOTES.md`. That is a different document from this one: this is the platform feedback
the **Most Valuable Feedback** award is judged on, and it names no measurement it did not take.*
