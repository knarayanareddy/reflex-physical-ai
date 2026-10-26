# Agent Delegation Protocol

How to hand these specs to autonomous coding agents so they produce merge-ready work instead of plausible fiction.
**Read this before dispatching your first ticket.**

---

## 1. Why this protocol exists

You have ~3.5 days and a team. You will be running many agent sessions in parallel. The three failure modes that
kill hackathon projects built this way are:

1. **Fabrication.** The agent invents an API signature, a regulatory clause number, a statistic, or a file path.
   In a hackathon judged on *"does the builder know where the problem is hard,"* one invented citation destroys
   credibility across the whole submission.
2. **Drift.** Two agents implement the same concept with different schemas and the integration fails at 2 a.m.
3. **Gold-plating.** An agent adds a vector DB, a queue, three integrations and a plugin system. Jackie, verbatim:
   *"I'd rather see one thing implemented really well and simply than a very large tech stack that doesn't need
   to be that complicated."*

The protocol below is designed to make all three detectable in the agent's own output.

---

## 2. The ticket contract

Every ticket in every `SPEC.md` has these fields. Dispatch a ticket by giving the agent **exactly** this block
plus the listed context files.

```
ID:          A-T07
TITLE:       Extract Article 19 fields from a listing
PHASE:       2
OWNER:       backend-agent
DEPENDS_ON:  A-T03, A-T06            ← do not start until these are DONE
BLOCKS:      A-T11, A-T14
CONTEXT:     ideas/_shared/platform-capabilities.md#2-token-factory-inference
             ideas/A-redflag-eu-product-safety/schemas/core-schemas.json#ListingFields
             ideas/A-redflag-eu-product-safety/data/gpsr-rules.v0.json
DELIVERABLE: backend/app/stages/extract_fields.py
             backend/tests/test_extract_fields.py
SPEC:        <precise requirements>
ACCEPTANCE:  <checkable statements, one per line>
VERIFY:      cd backend && uv run pytest tests/test_extract_fields.py -q
TIMEBOX:     3 agent runs. Then STOP and write BLOCKED.md.
```

### Rules for the agent (paste into every dispatch)

```
You are implementing ticket <ID> of a 4-day hackathon build. Follow these rules absolutely.

CORRECTNESS
1. Do NOT invent API signatures, parameter names, model IDs, endpoints, prices, statute article numbers,
   clause identifiers, dataset field names, or statistics. If you need one and it is not in your CONTEXT
   files, either (a) fetch the documented URL given in the ticket, or (b) write the literal string
   TODO_VERIFY(<what you need and where to look>) in the code and list it in TASK_REPORT.md.
   Never guess silently.
2. Do NOT fabricate data. Fixtures must come from data/fixtures/ or be clearly marked SYNTHETIC in the file.
3. If a CONTEXT file and reality disagree, reality wins. Record the disagreement in docs/DISCREPANCIES.md.

SCOPE
4. Implement ONLY this ticket. Do not refactor neighbouring code, do not add dependencies, do not add
   configuration options nobody asked for, do not add abstractions for hypothetical future use.
5. Allowed new dependencies: NONE, unless the ticket's SPEC explicitly names one. If you believe one is
   required, stop and write BLOCKED.md with the justification.
6. Do not touch frontend/src/tokens.css or any design token. Design is owned by a different ticket.

VERIFICATION
7. Run the VERIFY command. Paste its real output into TASK_REPORT.md. If it fails, fix it or report failure.
   Never claim success you did not observe.
8. Write tests before or alongside the implementation. Tests must fail if the implementation is removed.
9. Include at least one test that exercises the FAILURE path, not just the happy path.

OUTPUT
10. Produce: the diff, plus a new file reports/<ID>.TASK_REPORT.md containing:
      - WHAT: bullet list of what you built, with file paths
      - VERIFIED: the exact VERIFY command and its pasted output
      - COSTS: any model calls you made while developing, with token counts
      - TODO_VERIFY: every fact/API/clause you could not confirm, with where to confirm it
      - DEVIATIONS: anything you did differently from SPEC, and why
      - NOT_DONE: anything in ACCEPTANCE you did not satisfy
      - NEXT: the single most useful next ticket
11. If you cannot finish in TIMEBOX agent runs, stop and write reports/<ID>.BLOCKED.md containing:
      the precise question, what you tried, what output you got, and the two options you see.
      A good BLOCKED.md is a successful outcome. A plausible-looking wrong implementation is not.

INTEGRITY (this project is judged on honesty about its own limits)
12. If the system cannot determine something, it must say so. Implement abstention (UNDETERMINED) rather
    than producing a confident guess. This is a scored requirement, not a nicety.
13. Never let a language model's prose become a numeric measurement, a date, a legal citation or a
    verdict without passing through the deterministic gate. Route it through the gate or drop it.
```

---

## 3. Contract-first integration (prevents drift)

**Phase 1 exists only to freeze contracts.** After Phase 1:

- `schemas/core-schemas.json` is **frozen**. Any change requires a ticket of its own that lists every consumer
  and updates all of them in the same commit.
- Every pipeline stage implements the **same interface**:

```python
# backend/app/stages/base.py
from typing import Protocol, Any
from pydantic import BaseModel

class StageResult(BaseModel):
    stage: str
    ok: bool
    data: dict[str, Any]           # must validate against the stage's schema in schemas/core-schemas.json
    citation_ids: list[str] = []   # ids registered in the citation registry
    abstain: bool = False          # True => downstream must not treat data as a verdict
    abstain_reason: str | None = None
    cost_usd: float = 0.0
    latency_ms: int = 0
    ledger_ids: list[str] = []

class Stage(Protocol):
    name: str
    async def run(self, ctx: "RunContext") -> StageResult: ...
```

- **Citations are a first-class object with a registry.** A stage may not emit a `citation_id` that is not in the
  registry, and the registry entry must carry `locator`, `quote`, `retrieved_at` and (for fetched documents)
  `sha256`. The gate rejects any finding whose citations do not resolve. This single rule is what makes
  "verification" real instead of theatrical.

```json
{
  "id": "cit_01J...",
  "kind": "regulation | official_dataset | web_search | fetched_document | sandbox_run | measurement | user_input",
  "locator": "EUR-Lex 32023R0988 Art. 19(1)(a) | SR/02365/26 | https://... | runs/artifacts/pack_01.pdf",
  "quote": "the name, registered trade name or registered trademark ... and the postal and electronic contact details",
  "retrieved_at": "2026-10-27T09:14:02Z",
  "sha256": "…",
  "ttl_seconds": 604800,
  "trust": "primary | official_secondary | web | model_derived"
}
```

- **Parallel-safe lanes.** Assign each agent a disjoint set of paths. Never two agents in the same directory.

| Lane | Owns | Never touches |
|---|---|---|
| `data-agent` | `data/`, ingestion scripts, `jobs/` | `backend/app/stages/`, `frontend/` |
| `backend-agent` | `backend/app/stages/`, `backend/app/gate/`, `backend/app/tf/` | `frontend/`, `data/` |
| `sandbox-agent` | `backend/app/sandbox/`, artifact generation, branch A/B | `frontend/` |
| `frontend-agent` | `frontend/`, `tokens.css` | `backend/` |
| `eval-agent` | `backend/tests/`, eval harness, fixtures, batch scoring | production code |
| `content-agent` | `README.md`, `LIMITATIONS.md`, `docs/`, `video/` | code |

Integrate at fixed checkpoints (end of each phase), not continuously. A human runs `make check` at each
checkpoint; agents do not merge to `main` themselves.

---

## 4. The cite-or-abstain law (applies to every idea)

This is the architectural rule that separates your submission from the ~95 fact-checkers already in the field.

1. **The model proposes. The gate disposes.** An LLM may produce hypotheses, never verdicts.
2. **Every claim carries ≥1 citation object** that resolves in the registry.
3. **Every number comes from a measurement, not from prose.** If a distance, date, percentage, checksum or
   amount is needed, a deterministic function must produce it. The model may only *select* among measured values.
4. **Citations expire.** A `web_search` citation older than its TTL cannot support a verdict; it can only support
   a "verify this" suggestion.
5. **Abstain loudly.** If the gate cannot satisfy the above, the output is `UNDETERMINED` with a reason code and
   a routing instruction ("send to a human inspector" / "call your netbeheerder" / "not enough evidence").
6. **Show the gate rejecting something in the demo.** Suchismita asked of Telltale: *"what happens when the
   evidence is thin?"* Answer it on camera, deliberately.

---

## 5. Phase gates — what a human must check before the next phase starts

| Gate | Check | Pass condition |
|---|---|---|
| **G0 → G1** | `uv run pytest -q` green; one real Nemotron call logged in `runs/ledger.jsonl`; `LICENSE` at repo root; `tokens.css` authored; rules table v0 committed | All four artifacts exist |
| **G1 → G2** | Schemas frozen; every stage has a golden fixture test; skeleton services boot; `.env.example` complete | `make check` green from a clean clone |
| **G2 → G3** | **Thin slice works end to end on one real input**, ugly is fine | Screen-record it. This is your insurance |
| **G3 → G4** | Sandbox gate runs with networking disabled; batch job launched; ledger aggregates computed; A/B branch run complete | Numbers exist, not estimates |
| **G4 → G5** | Feature freeze. UI states complete. Deployed demo reachable from a **fresh incognito window on a different machine** | Send the URL to someone outside the team |
| **G5 → submit** | Video ≤2:50 rendered and **public on YouTube**; README has all required sections; LIMITATIONS has real numbers; Devpost feedback written; submitted with ≥24 h to spare | Submitted Thu 29 Oct by 18:00 CEST |

**Do not let an agent cross a gate.** A human verifies each one.

---

## 6. Prompt fragments worth keeping

**For the "insider insight" (Quality of the Idea, 25%).** Ask an agent:
> Given the domain brief below, list 15 things that are true in this domain that an intelligent outsider would
> not guess. For each, say what evidence would prove it and where that evidence is public. Rank by (surprise ×
> verifiability). Do not include anything you cannot point to a source for.

**For anti-gold-plating.** Append to any build ticket:
> Before writing code, list every component you are about to create and justify each in one sentence against
> the 30-second hook: "<paste hook>". Delete any component you cannot justify. Show me the deleted list.

**For the design agent (avoid the "Claude-built" tell).**
> Author `frontend/src/tokens.css` from this brief: <palette, mood, reference objects from the physical world>.
> Constraints: no purple-to-pink gradients; no glassmorphism; no default Tailwind colour names used directly in
> components — components may only reference `var(--…)` tokens; no emoji as iconography; no centred hero with
> three feature cards beneath it; no lorem ipsum anywhere. Provide both a dark (default) and a light theme.
> Every token must have a comment saying what it is for.

**For the eval agent.**
> Build a test set of N real cases. Label each twice, independently, by two different label sources (you and a
> fixture file). Report inter-annotator agreement (Cohen's kappa). Report per-class counts. Flag any class with
> fewer than 5 examples as INSUFFICIENT. Do not report an accuracy number on a set with an insufficient class.

**For the honesty pass (run last, on everything).**
> Read this README and this LIMITATIONS.md as a sceptical judge. List every sentence that is not backed by a
> number, a citation or a reproducible command. For each, propose either a source to add or a rewrite that is
> weaker but true. Do not soften claims that ARE backed.

---

## 7. Timeboxes and kill criteria

| Situation | Action |
|---|---|
| An agent has run 3× on a ticket without passing VERIFY | Human writes `BLOCKED.md`, ticket moves to the parking lot, **dependency chain re-planned within the hour** |
| A stage's data source is unreachable by Sun 26 Oct 20:00 | Trigger the documented **pivot** in that idea's SPEC §Risk Register. Do not spend Monday discovering this |
| Batch job has not produced numbers by Tue 28 Oct 18:00 | Shrink to 50 items and publish the smaller number honestly. A real n=50 beats a promised n=500 |
| The demo is not reachable from a fresh incognito window by Wed 29 Oct 12:00 | Freeze features. Everything else waits |
| Video is not shot by Wed 29 Oct 20:00 | Cut the video to the 90-second minimum viable version from the shot list. A submitted rough video beats an unsubmitted perfect one |

---

## 8. Definition of Done — global

A ticket is DONE only when:

- [ ] All `ACCEPTANCE` lines are satisfied
- [ ] `VERIFY` command run, real output pasted into `reports/<ID>.TASK_REPORT.md`
- [ ] At least one failure-path test exists and passes
- [ ] Every model/tool call made during development is in the ledger
- [ ] No `TODO_VERIFY` left unresolved, **or** each one is listed in `docs/DISCREPANCIES.md` with an owner
- [ ] No new dependency added outside the allowlist
- [ ] No design token touched
- [ ] Committed with a conventional message: `feat(A-T07): extract Article 19 fields from listing`
- [ ] `NOT_DONE` section honestly populated (empty is suspicious; agents always leave something)
