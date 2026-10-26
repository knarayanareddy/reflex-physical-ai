# Judging Rubric — decoded

Source: official Devpost rules for the Nebius × NVIDIA Global AI Hackathon, plus the full transcript of
**"Will It Ship? Inside the Judging Criteria with the Nebius x NVIDIA Hackathon Judges"** (Devpost, published
21 Oct 2026, recorded 20 Oct 2026, 56:41, `https://www.youtube.com/watch?v=LjCh-ZIyjx4`).
Raw transcript: `../../judges_transcript.txt`.

---

## 1. Scoring mechanics

**Two stages.**

- **Stage 1 — pass/fail eligibility & viability.** The project must reasonably fit the theme/track and must
  *genuinely* apply the required APIs/SDKs. Verbatim from the rules: *"a superficial rebrand of an unrelated
  idea is not sufficient."* Projects that fail Stage 1 are never scored.
- **Stage 2 — four criteria, equally weighted (25% each).** No published numeric scale.

| # | Criterion | Official wording |
|---|---|---|
| 1 | **Technological Implementation** | How well is the project built, and how effectively does it use Nebius Token Factory or AI Cloud model(s), and NVIDIA Nemotron as part of the solution? |
| 2 | **Design** | Does the project deliver a complete, coherent product experience — not just a technical proof of concept? |
| 3 | **Potential Impact** | Does the project make a credible, specific case for solving a real problem for a real audience, and does the solution actually address it based on what's demonstrated? |
| 4 | **Quality of the Idea** | Is this a creative, non-obvious use of Nebius Token Factory or AI Cloud model(s), and NVIDIA Nemotron — and does the team show genuine understanding of the problem space? |

**Tie-break order** (if scores tie): implementation → design → impact → idea. If still tied, judges vote.

**Award stacking — read this carefully:** *"Each Project is eligible for one (1) Overall Award OR one (1) Track
Award and one (1) Bonus Award."* So the $20,000 Grand Prize does **not** combine with a track Jetson or the
$3,000 Tavily prize. Do not design your submission around stacking.

**Prize table**

| Award | Value | Winners | Special eligibility |
|---|---|---|---|
| Grand Prize | $20,000 | 1 | All eligible |
| 2nd Place | $10,000 | 1 | All eligible |
| 3rd Place | $6,000 | 1 | All eligible |
| Coding & Agentic Engineering Track | Jetson Orin Nano | 1 | Entries in track |
| Best Apps & Agents Track | Jetson Orin Nano | 1 | Entries in track |
| Personal AI Track | Jetson Orin Nano | 1 | Entries in track |
| Physical AI Track | Jetson Orin Nano | 1 | Entries in track |
| **Best Use of Tavily** | **$3,000** | 1 | **A functional runtime call to the Tavily API as part of the solution** |
| City Winner Awards | $500 | 20 | Must attend a participating Builders & Brews city event |
| **Most Valuable Feedback** | **$100 + NVIDIA swag** | **10** | **Eligible submission completing the feedback section**; judged on completeness, viability and potential impact of the feedback |

Judging window **1–15 Dec 2026**; winners announced **~11 Jan 2027**. Your demo must remain available to judges
**free of charge and without restriction until judging ends** — a dead link in December is fatal.

---

## 2. The judge panel and what each one cares about

| Judge | Affiliation | Stated priority (from transcript) |
|---|---|---|
| **Jackie** | Senior Developer Advocate, Nebius | *"Are you actually using it… the different features… its capabilities and strengths."* Also: ease of trying the tool, smoothness, whether value is immediately inherent. Blends criteria 1+2. |
| **Ricky Johnson** | DevRel, Tavily (part of Nebius) | *"I love seeing unique core implementations… surprise core implementation."* And: *"should you build it?"* — market viability, real problem, talk to customers. Ties criteria 3+4. |
| **Suchismita Sahu** | Developer Relations Engineer, Tavily/NVIDIA (ex-NVIDIA, data-science background) | *"Honesty of what hasn't been done yet."* Aha moment **under two minutes**. Generic wrappers are not impactful. Wants: does the builder know where the problem is hard, the platform's strengths, tradeoffs between open models / model sizes / cost control, and **what you learned that someone outside the problem wouldn't know**. |
| **Selena Williams** | Technical Marketing Engineer, NVIDIA | Developer experience & UX, *"intuitive and intentional"*. Impact must be **seen through** simple design. Would personally weight **Potential Impact** highest. Warns that agent-built projects all look the same; differentiation comes from clarity of intent. |
| **Johnny Nunez** | Applied research, physical AI & robotics, NVIDIA | Wants **agentic** projects and *"local models running to apply on physical AI."* Prefers **small, real, daily-life** fixes over big ideas: *"the difficult is to do easy."* Values go-to-market / real products over paper-only research. |
| **Aditya** | Jetson team, NVIDIA | Persona clarity, fast concept of who it's for. Refine main features rather than add. Smooth reporting and UI. |

**Implication:** three of six judges are NVIDIA physical-AI/Jetson people. If you enter Physical AI you are
pitching to the panel's centre of gravity — in the track with ~4% of the field.

---

## 3. Verbatim judge guidance → concrete build requirements

| Verbatim | Concrete requirement |
|---|---|
| *"It should take you to the aha moment as quickly as possible — under two minutes."* (Suchismita) | Script and time the demo. A stranger reaches value in ≤120 s with zero narration. |
| *"Crystallizing that wow in 30 seconds or less… and what is the one thing they're actually taking away."* (Jackie) | Write the 30-second hook **before writing code**. One takeaway, stated in one sentence. |
| *"Right now it spends a lot of your top-quality screen space justifying why it made that decision, and the actual call to action isn't until the very bottom."* (Jackie, on Telltale) | **Verdict + action above the fold. Evidence collapsed underneath, expandable inline.** |
| *"Right now it feels like a very Claude-built app… I'd like to see a little bit more of the personal design touch."* (Jackie, on Telltale) | Author your own design tokens. No default AI purple/cream, no stock gradient hero, no emoji-as-iconography. |
| *"Something that could be a generic wrapper is not very impactful."* (Suchismita) | The LLM must be **non-interchangeable**. State what only Nemotron+Token Factory lets you do. |
| *"Does the builder know where the problem is hard? The tradeoffs between open models, multiple model sizes, cost control."* (Suchismita) | Publish a model-tiering table AND the measured cost of each tier, AND the cost delta vs a single-model baseline. |
| *"What did you learn about the problem that someone outside it wouldn't know?"* (Suchismita) | Your submission needs **one named insider insight**. Write it as a single sentence and say it in the video. |
| *"We now live in a time we can build anything. The more important question is, should you build it?"* (Ricky) | Justify existence: cite a real number from a real authority + one real person from the audience. |
| *"Get out and talk to potential customers before you build any features."* (Ricky) | ≥3 real conversations. One quotable line (with permission) in the video. |
| *"Does publishing your own failure cases and limitations help or hurt?" → "Absolutely a rigor… speaks higher to me than a super-polished product that fails once you dive in."* (Ricky, Suchismita, Aditya) | Ship `LIMITATIONS.md` with **real numbers and screenshots** of failures. Put one in the video. |
| *"I'd rather see one thing implemented really well and simply than a very large tech stack that doesn't need to be complicated."* (Ricky) | No dependency padding. Justify every service in the README. |
| *"Does it contribute to the main story? If it doesn't contribute to that 30-seconds-to-wow, maybe we should assess if it needs to be there."* (Jackie) | Cut any feature that doesn't serve the hook. |
| *"I hope to see some project related with local models running to apply on physical AI."* (Johnny) | Physical AI: put a **small model on-device** at the centre of the loop. |
| *"The difficult is to do easy… ideas that can fix your daily life."* (Johnny) | Prefer a narrow daily fix over a grand platform. |
| *"Budget more time than you expect for the final deliverables… packaging and narrative always takes longer than expected. Zero in on scope rather than adding."* (Selena) | Reserve the last full day for video + README + polish. |
| *"Accessibility always matters… share in next steps how you would plan to make the project more accessible."* (Selena) | One paragraph in Next Steps, minimum. |
| *"If you do put time into accessibility, make it as obvious as you can… it gets glazed over."* (Ricky) | Say it in the video, don't bury it. |
| Terminal UIs are fine: *"As an ops person, I love a terminal app"* — but reference **k9s** as the quality bar: surface the info that persona cares about (which model, how fast, cost) intuitively and uncluttered. (Jackie) | If you ship a CLI/TUI, show model attribution, latency and cost inline. |
| *"The final 90% is not necessarily easy to get to, but it's easier to get to that additional 10%. Final polish really sets you apart."* (Ricky) | Phase 5 exists. Do not skip it. |

---

## 4. The four projects the judges reviewed live — post-mortem

These are your best proxy for "what an actual submission looks like to a judge."

### Telltale — scam-message checker (Nemotron + Token Factory + Tavily)
*External verifier drops any claim it can't back up. Showed "5 proposed, 5 backed by evidence, 0 rejected."*

**Praised:** bright CTA that activates on paste; sample prompts to start; screenshot upload; clear hierarchy with
critical/bold/colour-coding; named tells ("urgency cue", "easy-money job bait"); links back to sources;
"what to do now / what not to do"; correctly handled a benign input as "low probability — probably legitimate."

**Lost points on:**
1. **CTA buried** — top screen space spent justifying the decision; the action was at the very bottom, below dense evidence.
2. **Aesthetic read as "Claude-built"** — no personal design touch.
3. **Unexplained UI** — a region dropdown with no explainer.
4. **Text-heavy / information-dense** — "there's a good chance they won't scroll all the way down."
5. **Competes with native OS/carrier scam flags** — Jackie flagged this but explicitly said *"I don't think that means you shouldn't build it."*
6. **Suggested improvements:** always-on integration (Gmail/message monitor), Chrome extension, connect to apps.
7. Tavily judge noted the web-search use was *"a great potential use case for Tavily"* — and it did use Tavily.

### slash-agent — cost-routing coding agent (Ultra plans, smaller Nemotron codes, Tavily release notes)
*Books the cheapest Nemotron model on Token Factory that can do each step, returns a receipt of spend and savings.*

**Praised:** the receipt concept — *"a smart move, at least it gives me something concrete to look at."*

**Lost points on:**
1. **No progress indicator** — cards pop up and you can't tell if it's still working or done.
2. **No stop button.**
3. **No routing visualisation** — a judge asked for a graph of which models are used and how routing proceeds.
4. **No baseline comparison** — *"here's what this job cost with routing versus what it would have cost on a bigger model. That would be intuitive."*
5. **Single-user lockout** — "another visitor's job is running." Fatal for a public demo judges all click at once.
6. **Onboarding unclear** — Jackie clicked every coloured button (fix/add) and couldn't tell what they did.

### Mnemos — auditable agent memory ("starry sky")
*Nemotron 3 Nano + Super + Ultra + a vision model on Token Factory, Qdrant embeddings, MCP server so other agents share the memory.*

**Praised:** beautiful — falling stars, meteor showers; the "what do you remember about me?" affordance; the
delete-a-memory-and-see-the-answer-change interaction; Jackie: *"this is a much prettier version of what I built for myself."*

**Lost points on:**
1. **The judge could not determine the use case.** *"What beyond that is the use case… impact is where I'm missing a little bit."*
2. The MCP-server angle — the actual differentiator — **took the judge three minutes to reach**, and only after another judge explained it: *"Sorry it took me a while to get there, but that makes sense."*
3. Ambiguity about whether memory was pre-seeded for the demo or a shared single server (a trust problem).
4. An unexplained popup that may have been an intro video — *"if it gave a sort of introduction, that's always super helpful."*

> **The lesson:** the prettiest submission lost the most, because legibility of purpose beats beauty.

### Assay — automatic QA for robot demonstration data (Physical AI)
*Flags bad demo episodes — bad grasp, frozen arm, very short clips — with evidence at the moment it goes wrong. Nemotron on Token Factory for the written summary.*

**Praised:** *"a tool that's rich with a lot of data and information"*; *"a lot of good objective hard rules they have employed for data analysis. That's pretty cool in terms of technical implementation."*

**Lost points on:**
1. **No onboarding / tooltip / guided tour** — judges had to click around blind. Ricky: *"so they're not jumping in having to click around themselves."*
2. **Default dataset dumped raw metadata** — needed defining/summarising.
3. **No visualisation of the report** — Jackie asked for *"a graph telling which cases are failing… what improvements can be done based on the analysis."*
4. A `standard error` appeared during the live run.

---

## 5. Scoring sheet to use on your own submission before you submit

Score each 0–10. **Anything below 7 → stop adding features and fix that criterion.**

### Technological Implementation
- [ ] ≥3 distinct Token Factory / AI Cloud features used and *shown on screen* (not just chat completions)
- [ ] Exact NVIDIA model IDs named in README and visible in the UI
- [ ] Model tiering table with the job each tier does and *why*
- [ ] Measured tokens + cost + latency, from an actual ledger, not estimates
- [ ] Cost delta published vs a single-large-model baseline
- [ ] Cached-token or batch savings quantified
- [ ] Sandbox used for something a plain API call can't do (branch / network-off / artifact)
- [ ] Serverless Jobs and/or Endpoints used where the track encourages them
- [ ] The LLM is non-interchangeable — you can say what breaks if you swap in a closed model

### Design
- [ ] A stranger reaches the aha in ≤120 s with no narration
- [ ] Verdict/action above the fold; evidence collapsed and expandable inline
- [ ] Own design tokens — palette, type scale, iconography. Not a default AI theme
- [ ] Every async action has a progress state AND a stop/cancel
- [ ] Empty, loading, error and partial-failure states all handled
- [ ] Onboarding: sample inputs one click away; first-run explanation
- [ ] No unexplained control anywhere in the UI
- [ ] Concurrent users don't lock each other out on the public demo
- [ ] Works on a 13" laptop and on mobile
- [ ] Keyboard navigable; ARIA labels; contrast checked; accessibility called out in the video

### Potential Impact
- [ ] One real, dated number from a named authority, on screen
- [ ] A specific persona named in their own words (not "businesses")
- [ ] ≥3 real conversations with the target audience; ≥1 quotable line with permission
- [ ] A batch run at scale producing **original aggregate statistics**
- [ ] The demonstrated solution actually addresses the stated problem (not adjacent to it)
- [ ] Competitive landscape acknowledged honestly (native tools, incumbents)

### Quality of the Idea
- [ ] One **named insider insight**, stated in one sentence, in README + video
- [ ] You can say precisely where the problem is hard
- [ ] The gate/verifier is the product, not decoration — show it rejecting something
- [ ] Abstention implemented: the system can say UNDETERMINED and route to a human
- [ ] `LIMITATIONS.md` with real failure cases, numbers, screenshots
- [ ] Not in the top-10 saturated clusters (see `competitor-landscape-833.csv`)

---

## 6. The winning architecture pattern (reverse-engineered from actual grand prizes)

Cross-hackathon evidence:

- **DataHub Agent Hackathon 2026, Grand Prize — "Blackbox."** One plain-English sentence ("revenue just jumped,
  is this real?") → reads lineage to localize → **proves root cause against a machine-enforced evidence gate** →
  repairs the code → runs the invariant suite → **opens a PR for a human** → **writes the resolution back** as an incident.
  Runners-up: *Hindsight* (walks lineage, writes a postmortem back), *Culprit* (traces model decay, **prices the damage**),
  *Paracelsus* (rejects the obvious severity axis and **borrows a risk model from toxicology**), *ContextSeal* and
  *RippleProof* (**prove a change safe before anyone implements it; stop when you can't prove it**).
- **AWS AI Agent Global Hackathon, 1st — EcoLafaek.** Citizen mobile reporting + autonomous agent chaining tools,
  classifying waste images, mapping pollution hotspots (Timor-Leste).
- **Microsoft AI Dev Days 2026, Grand Prize (Agentic DevOps) — PRism.** Multi-agent "release gate" asking
  *"what could this break in the real world?"*
- **Impetus × AWS GenAI Hackathon, $10k 1st — Privacy Guardian Agents.** "A privacy licence for codebases," multi-agent governance.
- **LlamaIndex Agentic RAG-a-thon, 1st — Timeline of You; 2nd — Closing.WTF** (mortgage closing docs → negotiation
  levers; judged on *"clear use-case and significant market potential"*).
- **NVIDIA Nemotron Developer Days Seoul 2026, Grand Prize — Nota AI.** A synthetic-data pipeline for MoE
  quantization built on Nemotron 3 Super. They **explicitly framed the outcome as plugging into NVIDIA's own NeMo
  Data Designer** — i.e. they made the sponsor's roadmap their payoff — and closed the pitch with a joke pointing
  at the DGX Spark prize. *They understood the room.*

### The formula

> **One sentence of pain**, in the persona's own words
> → **a machine-enforced gate** the model cannot talk its way past
> → **cited, re-runnable evidence** from a real public dataset, with retrieval timestamps and hashes
> → **a human-actionable artifact** you can hand to someone (a filing, a certificate, a PR, a letter, a report)
> → **tiered models**, cheap for volume and large for hard reasoning, **with the cost delta published**
> → **the ability to abstain** (UNDETERMINED → human)
> → **an honest limitations section with numbers**

Every line maps to a judge quote in §3. This is the rubric, restated as an architecture.
