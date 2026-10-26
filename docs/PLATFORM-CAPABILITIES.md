# Platform Capabilities Reference

Everything a build agent needs about Nebius Token Factory, Nebius AI Cloud Serverless, NVIDIA open models and
Tavily — plus which capabilities are **under-exploited by the field** and therefore worth showing on camera.

> **Agent rule:** never invent an API signature, parameter name, model ID or price. Every one of the following
> must be confirmed against the live docs URL given, at build time, before code depends on it. If the docs
> disagree with this file, **the docs win** — and record the discrepancy in `docs/DISCREPANCIES.md`.

---

## 1. Accounts, credits, keys

| Step | Where | Note |
|---|---|---|
| Token Factory account | `https://tokenfactory.nebius.com` | Google or GitHub sign-in |
| API key | Token Factory console | Also documented at `docs.tokenfactory.nebius.com/api-reference/introduction#authentication` |
| **$25 credits (promo)** | `https://nebius.com/promo-code` | Activation code **`NEBIUS-DEVPOST-GLOBAL26`** |
| **+$25 credits + Tavily + Nebius Academy** | `https://dev.nebius.com/builders` | Nebius Builders Program (free); also gets you office hours |
| AI Cloud console | `https://console.nebius.com` | For Serverless Jobs / Endpoints / Devlabs |
| Community | `https://discord.gg/nN58zxSTFR` | Channel **`devpostglobalaihackathon`** |

**Budget reality:** one competitor logged **38 requests / 669,899 prompt tokens / 230,964 completion tokens ≈
US$0.94** at catalog prices, using Nemotron 3 Ultra (550B MoE, 55B active) and Nemotron 3 Super (120B MoE, 12B
active). All Nemotron 3 models are MoE, so active params — and therefore price — are far below headline size.
**$50 is a lot of runway.** Do not ration; do run 200–500-item batches. Do log every token.

---

## 2. Token Factory inference

**Base URL:** `https://api.tokenfactory.nebius.com/v1/`
**Wire format:** OpenAI-compatible. The official quickstart literally uses the `openai` SDK:

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=os.environ["NEBIUS_API_KEY"],
)

resp = client.chat.completions.create(
    model="nvidia/Nemotron-3-Ultra-550b-a55b",   # CONFIRM exact ID against your authenticated catalog
    messages=[{"role": "system", "content": "You are a helpful assistant"},
              {"role": "user", "content": "hello"}],
)
```

### Model IDs observed in the wild (competitor repos calling the authenticated catalog)

| Model | Observed ID / name | Use it for |
|---|---|---|
| Nemotron 3 **Ultra** | `nvidia/Nemotron-3-Ultra-550b-a55b` (550B MoE, 55B active) | Hard reasoning. One competitor notes a **16,000-token output limit** on Ultra — verify and design around it |
| Nemotron 3 **Super** | `nvidia/nemotron-3-super-120b-a12b` (120B MoE, 12B active) | Mid-tier volume reasoning |
| Nemotron 3 **Nano** | *(confirm exact ID from your catalog)* | Fast/cheap calls, screening, classification, extraction |
| Vision model(s) | *(confirm from catalog)* | Photo/frame understanding |
| **Cosmos Reason** | e.g. Cosmos Reason 2 *(confirm)* | Video/world understanding — Physical AI |
| **Isaac GR00T** | e.g. GR00T N1.7 *(confirm)* | Humanoid/robot foundation model — Physical AI |
| **Parakeet** / **Canary** | *(confirm)* | ASR / speech |
| Non-NVIDIA also served | DeepSeek-R1-0528 (the docs' own example), GLM, MiniMax, Qwen embedding models | Fine to use, but **≥1 NVIDIA open-source model is mandatory** |

> **Task for Phase 0:** write a script that hits your authenticated `/v1/models` endpoint and dumps the exact
> catalog with prices into `data/model-catalog.snapshot.json`, committed to the repo. Then **pin every model ID
> in `.env` and reference the snapshot in the README.** That snapshot is itself Technological Implementation
> evidence — it proves you used the real catalog rather than a guessed ID.

### Documented inference capabilities (each a possible differentiator)

| Capability | Doc | Why it scores | Field usage |
|---|---|---|---|
| **Structured output / JSON** | `docs.tokenfactory.nebius.com/ai-models-inference/json` | Makes a deterministic gate possible: the model returns a schema, your code validates it. This is the mechanism behind every "evidence gate" winner | Common but rarely *shown* |
| **Function calling & tools** | `.../ai-models-inference/function-calling` | Turns a wrapper into an agent | Common |
| **Cached Tokens** | `docs.tokenfactory.nebius.com/cached-tokens` | Directly answers Suchismita's "cost control" ask. Report cache-hit savings from a long repeated system prompt | **Very rare** |
| **Rate limits & scaling** | `.../ai-models-inference/rate-limits` | You must know these to run a 250-item batch without 429s | Rare |
| **Inference Observability** | `.../ai-models-inference/observability` | Real latency/cost dashboards → your "receipt" with a baseline | **Rare** |
| **Observability API integrations** | `.../observability-api-integrations` | Pipe traces into an external tool | **Rare** |
| **Public Serverless Endpoints** | `docs.tokenfactory.nebius.com/public-serverless` | Cheapest always-on serving | Occasional |
| **Dedicated endpoints** | `.../ai-models-inference/dedicated-endpoints/overview` (+ quickstart, deploy-api, deploy-ui, capacity-and-scaling, billing-policy, lifecycle-and-status, best-practice, custom-weights) | Predictable latency/cost/data control; supports **custom model weights** | **Rare** |
| **UI & Playground** | `.../ai-models-inference/playground` | Good for the video's "here's the model in the catalog" shot | — |
| **Post-training: SFT (LoRA + full)** | `docs.tokenfactory.nebius.com/post-training/*` (`overview`, `datasets`, `models`, `how-to-fine-tune`, `custom-speculator`, `merge-moe-lora-weights`) | **A small LoRA on Nano with synthetic data is the single highest-leverage differentiator for 4 days' work.** This is exactly what won NVIDIA's Seoul Nemotron hackathon | **Very rare** |
| **Data Lab** | `docs.tokenfactory.nebius.com/data-lab/*` (`overview`, `chat-completions` import, `fine-tuning`, `data-processing`, `datasets`) | Turn your own logged traffic into a dataset | **Very rare** |
| **Batch / data processing** | via Data Lab + Serverless Jobs | Process hundreds of records and report **aggregate statistics** — converts a toy demo into a study | **Rare** |
| **Third-party integrations** | `.../integrations/overview` | Framework support | Occasional |

---

## 3. Token Factory Sandboxes — the strongest under-used primitive

Docs root: `docs.tokenfactory.nebius.com/sandboxes/overview`
Tagline from the docs: *"Give applications and AI agents an isolated environment to execute code, evaluate
results, and work with files."*

### Concepts you must understand

| Concept | Doc | What it gives you |
|---|---|---|
| **Execution lifecycle** | `.../sandboxes/concepts/execution-lifecycle` | Operations, processes, client waits, **event streams (SSE)**, saved images |
| **Images, checkpoints, branches** | `.../sandboxes/concepts/images-checkpoints-and-branches` | *"Save filesystem state deliberately and start independent work from immutable images."* → **branch-and-compare = you can PROVE a counterfactual instead of claiming it** |
| **Sessions and execution modes** | `.../sandboxes/concepts/sessions-and-execution-modes` | Client workflow state vs operations vs live processes |

### Guides

- `run-commands-and-results` — command vs shell execution, explicit persistence, interpreting results
- `stream-output-and-events` — **stdout/stderr over SSE, resume after disconnect**, verify final result
- `run-subprocesses-and-send-input` — spawn a child process inside an active operation, exchange input, send signals
- `prepare-and-reuse-environments` — reusable filesystem image from setup commands, OCI import, or the supported CLI Dockerfile subset
- `work-with-files-and-artifacts` — inject files, retain generated artifacts, inspect images, **download bytes after execution**
- `branch-compare-and-recover` — *"Run alternatives from one image, select a verified result, and recover from a known-good checkpoint."*
- `configure-networking-and-secrets` — **disable the guest network where supported**; keep credentials out of retained state and output
- `run-concurrent-workloads` — bound parallel operations, correlate state, classify failures, cancel only work owned by the batch

### Cookbook (each of these is a ready-made demo beat)

| Cookbook | What it proves |
|---|---|
| `prepare-once-reuse-safely` | One prepared image reused across independent later operations |
| `stream-a-build-or-test-run` | Deterministic test suite, streamed stdout/stderr, **verify both success and failure** |
| `interact-with-a-process` | Spawn child, send inputs + EOF, test signals, clean up on failure |
| **`try-two-coding-fixes`** | *"Apply two isolated patches to failing deterministic tests, select the passing image, and continue from it."* → **this is your A/B gate proof** |
| `generate-and-download-binary-artifact` | Produce a deterministic binary, retain it, download it, **verify exact bytes locally** → hash your artifact |
| `build-reusable-custom-environment` | Build the supported Dockerfile subset, resolve the immutable UUID, run twice, refresh after a source change |
| **`verify-with-networking-disabled`** | *"Save prepared inputs, verify them without a guest network interface."* → **prove no data exfiltration / no cheating / no live lookups** |
| `run-bounded-evaluation-batch` | Correlate item, operation and image IDs; classify outcomes; cancel only your own work |
| `recover-from-known-good-image` | Diagnose a deliberate failure, retry corrected work from the recorded checkpoint |

### Interfaces
- **Python SDK**: `.../sandboxes/sdk/python_sdk/{getting-started, images, running-commands, branching}` + reference for `client`, `images`, `files`, `image`, `session`, `image_fs`, `subprocess`, `oci`
- **CLI**: `auth`, `use`, `run`, `build`, `images`, `tag`, `operation`, `ps`, `show`, `kill`, `ls`, `cat`, `grep`, `cp`, `cd`, `env`, `file`, `session`, `shell`, **`skill`** (install agent skills), **`agent`** (coding-agent manual)
- **REST API** and **MCP** — see `.../sandboxes/reference/index` for the compatibility map
- Integrations: **Mini-SWE-Agent**, **LangChain**
- `.../sandboxes/swe-agents` — Sandboxes for SWE agents
- Ops: `.../sandboxes/operate/{troubleshooting, limits-retention-and-usage, security-and-data-handling}`

### The two Sandbox plays almost nobody in the field is making

1. **Network-off verification.** Generate an artifact, then validate it inside a Sandbox **with the guest network
   disabled**. Now your output is *provably* self-consistent and *provably* not silently calling the internet.
   Show the `network: disabled` flag on screen.
2. **Branch A/B.** Save one immutable image. Branch it. Run the **same test set** down both branches — one with
   your gate enabled, one with it bypassed. Publish the delta in false-accept / false-reject rate. You have just
   produced an *experiment*, and no amount of prose beats an experiment for Technological Implementation.

The CLI `skill` command also maps directly onto the **Personal AI track's** language ("reusable skills") — free
alignment if you pivot track.

---

## 4. Nebius AI Cloud — Serverless AI

Docs: `docs.nebius.com/serverless/overview`
Console: `console.nebius.com/serverless/{job,endpoint,devlab}`

*"Build and deploy Serverless AI jobs and endpoints from your container in minutes, without managing Kubernetes
or infrastructure."*

| | **Devlab** | **Job** | **Endpoint** |
|---|---|---|---|
| Use case | Code/explore in browser IDE or notebook | Preprocess data, train, fine-tune, **batch inference**, **evaluate models**, run scientific simulations | Host a model or app at a URL for **real-time inference**, A/B test |
| Workflow | Interactive, long-lived, start/stop | **Non-interactive, terminates on completion or timeout** | Interactive, responds until terminated |
| Stop/start | Yes | **No** | Yes |
| **Public URL** | Yes (web UI + declared ports) | **No** | **Yes** |
| Storage | Workspace path on container disk persists across stop/restart | **Container disk removed when job finishes/is deleted** | Container disk removed when stopped/deleted |
| Typical lifetime | Minutes → days | Minutes → days | Hours → days |

- Quickstarts: `serverless/quickstart/{devlabs,jobs,endpoints}`
- Managing: `serverless/{devlabs,jobs,endpoints}/manage`
- Tutorials — all directly reusable:
  - `serverless/tutorials/deploy-model` — deploy an LLM and chat via a Serverless Endpoint
  - `serverless/tutorials/fine-tuning` — **fine-tune an LLM with a Serverless Job and Axolotl**
  - `serverless/tutorials/tts` — speech synthesis
  - `serverless/tutorials/video-translation` — video translation & dubbing
  - `serverless/tutorials/openmm-molecular-dynamics` — molecular dynamics sims
- Lifecycle/statuses `serverless/lifecycle`; metrics `serverless/monitoring`; **automatic job restarts**
  `serverless/jobs/auto-restarts`; debugging failures `serverless/jobs/failure`; pricing/quotas `serverless/pricing-quotas`
- Observability: each deployment has a status, **logs**, and **GPU / vCPU utilization metrics** in the console.
- Billing: per-second, usage-based, follows Compute billing/quota rules. Stopped Endpoint = no compute or storage
  billing. Stopped Devlab = container disk still billed. Mounted Object Storage buckets / shared filesystems
  billed separately, even when stopped.

**Both the Best Apps & Agents track and the Physical AI track explicitly encourage Serverless Endpoints
(deployment) and Serverless Jobs (background processing / async workflows / simulations / synthetic data /
policy evaluation / sensor data at scale).** Using them is close to free points and is named in the track text.

**Other AI Cloud services** (see `docs.nebius.com/llms.txt` for the full index): GPU Compute VMs, InfiniBand
clusters, Managed Kubernetes, **Slurm / Soperator** (`slurm-soperator/*`, including batch jobs and moving
capacity between training and inference), Object Storage (S3-compatible), Managed PostgreSQL, networking.
There is an official RAG tutorial: `docs.nebius.com/tutorials/rag` (JupyterLab + Serverless AI + Managed PostgreSQL).

---

## 5. Tavily — the $3,000 bonus prize

- Prize requirement: **"a functional runtime call to the Tavily API as part of the solution."** Decoration does
  not qualify; the call must be load-bearing.
- Docs: `docs.tavily.com/welcome`; app: `app.tavily.com/home`
- Capabilities: real-time **web search** and **content extraction** for LLMs and agents, via API and SDKs.
- Free credits via the **Nebius Builders Program**; event attendees got additional Tavily credits.
- Two Tavily DevRel people sit on the judge panel (Ricky Johnson, Suchismita Sahu).

**Make it load-bearing in a way you can demonstrate:** log every Tavily call with query, timestamp, result count,
and the citation IDs it produced. Surface it in the UI as *"live check performed at 14:32:07 CEST — 6 sources,
2 used, 4 rejected as stale."* Then, in the video, show the **same query returning a different answer a week
later** — that's proof it's live, not baked.

---

## 6. Other NVIDIA tooling named in the track descriptions

| Tool | Named in | Note |
|---|---|---|
| **NVIDIA NemoClaw** | Personal AI track | *"tools such as NVIDIA NemoClaw, OpenShell, Hermes Agent, and Nebius Serverless to bring personal AI to assemble, secure, and run your own personal AI system."* Confirm current docs/availability at build time |
| **OpenShell** | Personal AI track | A competitor used it for sandboxing a study copilot |
| **Hermes Agent** | Personal AI track | Also appears in the DevNetwork hackathon ("Build a Hermes / NemoClaw agent running Nemotron") |
| **NeMo Guardrails** | — | A competitor (`clinicdesk`) used it with Nemotron |
| **NeMo Data Designer** | — | What the Seoul grand-prize winner name-dropped as their downstream. Referencing NVIDIA's own roadmap as your payoff worked |
| **Isaac Sim / Isaac GR00T / Cosmos** | Physical AI track | *"powered by Nemotron, GROOT, Cosmos and Sonic models"* |
| **Jetson (Orin Nano)** | Physical AI track prize | The prize itself. Johnny + Aditya are the Jetson/physical-AI judges |

> **Agent rule:** NemoClaw, OpenShell, Hermes Agent and "Sonic" are named in the hackathon copy but their public
> docs may be sparse or gated. **Verify availability before depending on them.** If unavailable, say so in
> `LIMITATIONS.md` — that is itself good feedback for the $100 Most Valuable Feedback prize.

---

## 7. Standard stack for all four ideas (freeze this)

Keeping one stack across ideas lets shared docs apply and reduces agent failure modes.

| Layer | Choice | Why |
|---|---|---|
| Language / runtime (backend) | **Python 3.12**, managed by **`uv`** | Fast installs, lockfile, agents handle it well |
| Web framework | **FastAPI** + **Pydantic v2** | Pydantic v2 = your structured-output validation layer |
| Data store | **DuckDB** (embedded, file-backed) | Zero-ops SQL over Parquet/CSV; perfect for the Safety Gate corpus and batch runs |
| Embeddings | A Qwen/OpenAI-compatible embedding model on Token Factory, or `sentence-transformers` locally | Confirm availability in your catalog |
| HTTP | `httpx` (async) | |
| Browser automation | **Playwright** (headless Chromium) | For live listing / document retrieval. Pin the version; ship pre-cached fixtures so the demo never depends on it |
| Async/task queue | `arq` or plain `asyncio.Queue` + a SQLite/DuckDB job table | Avoid Celery/Redis — Jackie: don't build a monolith |
| Frontend | **Vite + React 18 + TypeScript + Tailwind CSS** | Simple, fast, agent-friendly. **No component library defaults** — author `tokens.css` by hand |
| Charts | **Recharts** or hand-rolled SVG | For the batch-study and A/B charts |
| PDF/report artifact | **WeasyPrint** (HTML→PDF) or ReportLab, run **inside the Sandbox** | So the artifact is provably sandbox-generated and hash-verifiable |
| Backend deploy | **Nebius Serverless Endpoint** (named in track text) or a small VPS/Render/Fly | Serverless Endpoint scores better |
| Frontend deploy | Cloudflare Pages / Vercel / Netlify free tier | Must stay **free and unrestricted until 15 Dec 2026** |
| Tests | `pytest`, `pytest-asyncio`, `httpx` test client | Golden-fixture tests for every stage |
| Instrumentation | A single append-only **JSONL ledger** (`runs/ledger.jsonl`) written by a wrapper around every model/tool call | This ledger *is* your Technological Implementation evidence |
| CI | GitHub Actions: `ruff` + `pytest` + `tsc --noEmit` + build | Proves the repo runs |
| Licence | **Apache-2.0** (or MIT / MPL-2.0) **file at repo root** | Explicit submission requirement; Stage-1 filter |

### Repo layout (identical shape for all four ideas)

```
<project>/
├── LICENSE                        ← Apache-2.0, AT REPO ROOT, visible on the repo page
├── README.md                      ← see _shared/templates/README.template.md
├── LIMITATIONS.md                 ← see _shared/templates/LIMITATIONS.template.md
├── ARCHITECTURE.md
├── .env.example                   ← NEVER commit .env
├── .github/workflows/ci.yml
├── docs/
│   ├── MODEL-USAGE.md             ← tiering table + measured costs
│   ├── DISCREPANCIES.md           ← anywhere live docs disagreed with our assumptions
│   └── DECISIONS.md               ← one line per significant decision + why
├── data/
│   ├── model-catalog.snapshot.json
│   ├── fixtures/                  ← golden inputs (cached listings/photos/docs)
│   └── corpus/                    ← ingested public datasets (or a fetch script + .gitignore)
├── schemas/                       ← FROZEN contracts. Changing one requires updating all consumers
│   └── core-schemas.json
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py                ← FastAPI app
│   │   ├── config.py              ← pydantic-settings; all model IDs + keys from env
│   │   ├── tf/                    ← Token Factory client wrapper + LEDGER
│   │   │   ├── client.py
│   │   │   ├── ledger.py
│   │   │   └── cache.py           ← cached-token accounting
│   │   ├── stages/                ← one module per pipeline stage, same interface
│   │   ├── gate/                  ← the deterministic gate + rules table loader
│   │   ├── sandbox/               ← Token Factory Sandboxes wrapper (images/branches/network-off)
│   │   ├── tools/tavily.py
│   │   └── citations.py           ← citation registry: id → locator, quote, retrieved_at, sha256
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── src/tokens.css             ← the design system. DO NOT use a stock theme
│   ├── src/components/
│   └── src/routes/
├── jobs/                          ← Nebius Serverless Job entrypoints (batch study)
│   ├── Dockerfile
│   └── batch_run.py
├── runs/                          ← ledger.jsonl, reports, generated artifacts (gitignored except samples)
└── video/
    ├── script.md
    └── shots/
```

### The ledger contract (write this once, use it in every idea)

Every model call, Tavily call and Sandbox operation appends one line to `runs/ledger.jsonl`:

```json
{
  "id": "led_01J...",
  "run_id": "run_01J...",
  "ts": "2026-10-28T14:32:07.114Z",
  "kind": "chat.completions | embeddings | tavily.search | tavily.extract | sandbox.operation | sandbox.branch",
  "stage": "extract_fields",
  "model": "nvidia/Nemotron-3-Ultra-550b-a55b",
  "request": {"prompt_tokens": 18412, "completion_tokens": 604, "cached_tokens": 17920, "tools": 3},
  "response": {"finish_reason": "stop", "valid_json": true, "schema_ok": true},
  "cost_usd": 0.0312,
  "latency_ms": 4180,
  "status": "ok | error | truncated | schema_violation | gate_rejected",
  "error": null,
  "citation_ids_produced": ["cit_07","cit_08"],
  "notes": "Ultra invoked only because Nano returned applicability_confidence=0.41 < 0.75"
}
```

**Then publish aggregates from it:** total requests, total tokens, total cost, cache-hit rate, p50/p95 latency per
model, per-stage cost, failure count by class, and **the counterfactual cost of routing everything to Ultra**.
That last number is the baseline comparison the judges explicitly asked slash-agent for and it did not have.
