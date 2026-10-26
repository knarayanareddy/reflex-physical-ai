# video-script.template.md — the only thing some judges will consume

**Used by:** A-T40 / B-T40 / C-T40 / D-T36. Copy, fill every `<…>`, delete this header.

> **Constraints, non-negotiable.**
> - **≤3:00.** Judging runs 1–15 Dec across hundreds of projects; a 4-minute video gets skipped at 2:30. Aim for
>   **2:30–2:50** so you are safely under.
> - **Public** YouTube (unlisted is fine only if the rules allow it — check; Devpost needs to embed it). Verify the
>   link works in a logged-out incognito window.
> - **Captions on.** Not auto-captions left uncorrected — read them once and fix the technical terms. A judge
>   watching muted in an office is a real case.
> - **No copyrighted music.** No third-party logos used as branding or to imply endorsement.
> - **Physical AI track: ≥1 minute of footage showing the hardware or modules in use.** Budget **1:30** so you are
>   safely over, and keep the money shot continuous and unbroken.
> - **No demo URL is required for Physical AI** — deploy one anyway.

> **What wins.** In the judges' own review session, the submissions that landed were the ones that showed a real
> input producing a real output on screen, named the models and platform features they used, and were honest about
> what they had not done. The ones that lost points asserted capability without showing it, or showed a UI with no
> pipeline behind it.
>
> **Structure that reliably works: problem → the thing only an insider would know → the artifact → the refusal →
> how it works → the proof → limitations.** That is seven beats in 150–170 seconds. Do not add an eighth.

---

## Beat sheet (target 2:40)

| # | Beat | Time | What is on screen | What is said |
|---|---|---|---|---|
| 1 | **The problem, in a human voice** | 0:00–0:15 | <the persona, or the artefact of the problem: a suppressed listing, a bad joint, an empty roof, a rig mid-motion> + one public statistic **with its source and date** on screen | One sentence of pain, in the persona's words. Then the number, attributed. |
| 2 | **The insider insight** | 0:15–0:35 | <the component that embodies it: the two DirectionCards showing different verdicts for one address; the Class 1/2/3 slider flipping a verdict live; the recalled-twin card with both photos> | "Here is what someone outside this domain would not guess: **<insight, one sentence>**." Show it, then say it — never the reverse. |
| 3 | **The artifact** | 0:35–1:05 | <the real input → the real verdict → the downloadable artifact being opened> | What you get, and what you can do with it in the next five minutes. Read the verdict aloud exactly as rendered. |
| 4 | **The refusal** ← do not cut this | 1:05–1:25 | <an input that produces UNDETERMINED / NO_OFFICIAL_POSITION_FOUND / an abstention, with the reason code and the fix instruction visible> | "And when it cannot verify, it says so: **<read the abstention aloud>**. It will not <invent a date / grade an uncalibrated joint / clear a veto>." |
| 5 | **How it works** | 1:25–1:55 | <the architecture diagram, animating stage by stage, with each model tier labelled> | Name the tiers and **why each one**. Name Token Factory Sandboxes, the Serverless Job, Tavily, structured output, cached tokens. Name the gate: "pure Python, no LLM — here is the test that proves it." |
| 6 | **The proof** | 1:55–2:25 | <the A/B chart, the eval table, the ledger, the replay compare — real numbers, real n> | "n=<n> per arm. With the gate on: <x>. With it off: <y>. Total cost: $<z>, and $<w> if we had used the largest model everywhere." |
| 7 | **Limitations + what's next** | 2:25–2:40 | <LIMITATIONS.md scrolling briefly; then the closing frame with the repo and demo URLs> | Say the biggest limitation **out loud**, with its number. Then one sentence on what's next. Then the takeaway. |

---

## Per-idea shot lists

Fill this in for your idea, then shoot it. Every shot gets an **owner** and a **take count** — assume 3 takes
minimum for anything live.

### Idea A — RedFlag
```
S01  0:00  2s   STILL   A real marketplace listing, the required-field gaps highlighted in amber
S02  0:02  6s   VO+TEXT The persona's sentence + the sweep statistic with its source and date
S03  0:08  4s   SCREEN  Paste the URL. The progress rail lights S1→S2→S3
S04  0:12  6s   SCREEN  THE VERDICT: "WOULD BE SUPPRESSED — 2 of 5 required fields missing"
S05  0:18  8s   SCREEN  The recalled-twin card: BOTH photos side by side, the alert number, the risk type
S06  0:26  5s   SCREEN  "Copy for Amazon" → the ready-to-paste correction text
S07  0:31  6s   SCREEN  Expand the evidence drawer: every citation with its retrieval timestamp and sha256
S08  0:37  8s   SCREEN  THE INSIGHT SHOT: a compliant-looking listing that is nonetheless AT_RISK because of a
                        recall twin. Caption: "Compliance is not a checklist problem, it's a recall-prior problem."
S09  0:45  6s   SCREEN  THE REFUSAL: an UNDETERMINED verdict with its reason code and fix instruction
S10  0:51  4s   SCREEN  The Sandbox PDF artifact opening; the sha256 match visible
S11  0:55 12s   SCREEN  Architecture animation, stage by stage, tiers labelled
S12  1:07  6s   SCREEN  Sandbox validation with the GUEST NETWORK DISABLED; the hash comparison
S13  1:13 10s   SCREEN  The A/B branch chart: gate-on vs gate-off over the same 120 cases
S14  1:23  8s   SCREEN  The batch sweep results: n listings, 3 categories, the table
S15  1:31  6s   SCREEN  The ledger: total cost, all-Ultra counterfactual
S16  1:37 10s   SCREEN  LIMITATIONS.md scrolling; the coverage table
S17  1:47  5s   CARD    Repo + demo URLs, the disclaimer, the takeaway sentence
```

### Idea B — JointCheck
```
S01  0:00  3s   MACRO   A real solder joint, close and slightly ugly. No music swell.
S02  0:03  5s   VO      The persona's sentence + one public statistic with source and date
S03  0:08  4s   SCREEN  Drop the photo in. S1 calibration check runs
S04  0:12  6s   SCREEN  THE CALIBRATION SHOT: the printed A4 target detected, mm/px computed, overlay shown.
                        Caption: "You cannot measure a fillet without a scale."
S05  0:18  6s   SCREEN  S2: CV proposes ROIs; the vision model confirms and names them
S06  0:24  8s   SCREEN  S3: the pure-OpenCV measurements appearing on the joint — fillet area, coverage %, wetting
                        angle — each with its pixel derivation
S07  0:32  6s   SCREEN  S4: the condition code from the frozen vocabulary, marked measurement_basis="measured"
S08  0:38 10s   SCREEN  **THE INSIGHT SHOT**: drag the Class slider 1 → 2 → 3 and watch the verdict flip from
                        ACCEPT to PROCESS_INDICATOR to REJECT in <200 ms. Caption: "Acceptability is a property
                        of the joint AND the reliability class." Show the regrade timer — it is instant because
                        S5–S6 are pure Python
S09  0:48  6s   SCREEN  S7: the PDF report opening; sha256 match
S10  0:54  8s   SCREEN  THE REFUSAL: an uncalibrated image → UNDETERMINED "uncalibrated" → the fix instruction
                        ("re-shoot with the target beside the board")
S11  1:02  5s   SCREEN  A downgraded claim in the UI: the model asserted a number it could not cite; the code
                        downgraded it to visual_only. Caption: "The model may not introduce a number."
S12  1:07 12s   SCREEN  Architecture animation, 7 stages, tiers labelled
S13  1:19  6s   SCREEN  Sandbox validation, network disabled
S14  1:25 10s   SCREEN  The A/B branch at Class 3, n per arm, the false-accept delta
S15  1:35  8s   SCREEN  The eval table: kappa, per-class confusion matrices, INSUFFICIENT flags
S16  1:43  8s   SCREEN  Ledger: text tokens and IMAGE TOKENS REPORTED SEPARATELY; all-Ultra counterfactual
S17  1:51 10s   SCREEN  LIMITATIONS.md; then the standards disclaimer, read aloud
S18  2:01  5s   CARD    URLs + takeaway
```

### Idea C — GridQueue
```
S01  0:00  4s   B-ROLL  An empty workshop roof, or a distribution board. Real, not stock.
S02  0:04  6s   VO+TEXT The persona's sentence + the interview cost-of-delay figure, attributed
S03  0:10  5s   SCREEN  Type the postcode and what you want to connect: "60 kW PV + 20 kW battery + 2× 22 kW"
S04  0:15 10s   SCREEN  **THE INSIGHT SHOT #1**: the two DirectionCards render side by side, same address —
                        "FEED-IN: no firm capacity" / "CONSUMPTION: 25 kW may be available".
                        Caption: "Capacity has a direction. Most tools don't ask which one."
S05  0:25  8s   SCREEN  Expand the date claim → the BindingChip reads NON-BINDING → open the revision history →
                        "this forecast moved from Q1 2028 to Q3 2028", with both quotes.
                        Caption: "A codeerprognose is not a promise, and it moves."
S06  0:33  8s   SCREEN  THE INSIGHT SHOT #3: the ranked options with computed kW, the half-hourly load profile,
                        and the Dutch phone script being copied
S07  0:41  5s   SCREEN  The application pack PDF opening; sha256 match
S08  0:46 10s   SCREEN  **THE REFUSAL**: a postcode with no official position → NO_OFFICIAL_POSITION_FOUND →
                        the phone script. Caption: "It will not invent a date. That is the product."
S09  0:56 12s   SCREEN  Architecture animation; Tavily shown as a runtime dependency with results-used /
                        results-rejected visible
S10  1:08  6s   SCREEN  Sandbox validation with the network disabled; hash comparison
S11  1:14 10s   SCREEN  The A/B chart: invented dates, gate-off vs gate-on, n=60 per arm
S12  1:24  8s   SCREEN  /corpus — the full public source list with hashes and retrieval timestamps
S13  1:32 10s   SCREEN  /sweep — the map, n areas, the methodology box
S14  1:42  6s   SCREEN  Ledger: cost, cache-hit rate, all-Ultra counterfactual
S15  1:48  8s   SCREEN  LIMITATIONS.md; the coverage table naming the operators NOT covered
S16  1:56  6s   CARD    The framing sentence: "a generalisable pipeline, demonstrated where the data is worst."
                        URLs + disclaimer
```

### Idea D — Reflex
```
⚠ ≥1:00 of hardware footage is REQUIRED. Budget 1:30. Keep the veto take CONTINUOUS — a jump cut during the veto
  destroys the proof.

S01  0:00  4s   HARDWARE  Locked-off wide shot of the whole rig: rail, pusher, object, taped keep-out volume,
                          relay module. Point at each with a hand or a pointer.
S02  0:04  4s   HARDWARE  Say the parts cost on camera. €<n>. It is a credibility signal, not a weakness.
S03  0:08  6s   TEXT      The problem: "~34 of 833 public submissions touch physical AI, and almost none show
                          what the system REFUSED to do."
S04  0:14 30s   HARDWARE  **THE VETO, ONE CONTINUOUS TAKE.** Split screen: camera left, telemetry right. A goal
                          goes to Ultra → proposals stream → the actuator moves → the intruder enters the keep-out
                          volume → the envelope vetoes within one frame → **CUT TO THE RELAY CLOSE-UP SO THE CLICK
                          IS AUDIBLE** → the pusher stops → a ledger line appears on screen.
                          Caption: "No network. No model. Pure deterministic code with hardware authority."
S05  0:44  8s   HARDWARE  Re-shoot from another angle if useful: the intruder object on a string, the stop
                          distance marked on the bench with tape and a ruler
S06  0:52  8s   SCREEN    THE LAW, proven: `make verify-envelope` → PASS. Then the test showing a Cosmos Reason
                          "workspace clear" response CANNOT clear a veto.
                          Caption: "A large model cannot talk this out of stopping."
S07  1:00 10s   SCREEN    THE PROOF: ReplayCompare — envelope_off collides, envelope_on clean. Same image, same
                          seed. Then the numbers: <n> vetoed, <n> replayed, 0 collisions shipped, and the
                          conservative fraction stated honestly.
S08  1:10 12s   HARDWARE  **INSIGHT #3, FILMED: pull the network cable.** ModeBadge flips to DEGRADED, the
                          parameter diff appears, the rig keeps working under stricter limits, the ledger shows
                          zero lost decisions. Caption: "It fails safe, not open."
S09  1:22 10s   SCREEN    The local model running ON THE DEVICE, with its real throughput number on screen.
                          (This is the judge's stated ask — do not bury it.)
S10  1:32 12s   SCREEN    Architecture: the Cloud/Edge split, tiers labelled; Serverless Job for the replay lane;
                          Sandbox branching for byte-identical arms
S11  1:44 10s   SCREEN    The session statistics table: veto-to-stop latency and distance, edge vs cloud latency,
                          cost per 1,000 actions, false-positive rate
S12  1:54 12s   SCREEN    SAFETY-CASE.md and LIMITATIONS.md. **Read the non-certification statement aloud:**
                          "This is a research prototype, not a certified safety system."
S13  2:06  6s   CARD      URLs + the takeaway sentence
```

---

## Voice-over rules

- **Read the verdicts, reason codes and abstention messages aloud exactly as they render.** Paraphrasing them
  weakens the strongest evidence you have.
- **Never say a number you have not published somewhere in the repo.** A judge who checks one number and finds it
  unsupported stops believing all of them.
- **Attribute every statistic on screen**: source and date, in small type, in the frame where it appears.
- **Attribute every human quote**: first name, role, date, "used with permission".
- Name the models by their real catalog names at least once each. Name the Nebius features by their real names
  (Token Factory Sandboxes, Serverless Job, Serverless Endpoint, cached tokens, structured output).
- Do not narrate what is visibly happening on screen ("now I click the button"). Narrate what it *means*.
- **Silence is fine for 2 seconds** during the money shot. Do not fill it. The relay click needs silence under it.
- Total spoken words for 2:40 at a natural pace: **roughly 380–420**. Count yours. If it is over 460 you are
  rushing and it will sound like an advert.

## Shooting rules

- Lock the camera. A handheld shot of a safety system reads as amateur.
- Screen recordings at native resolution — **never film a monitor**.
- Light evenly and diffusely; avoid a window in shot (a passing cloud changes your detection and wrecks a take).
- Shoot the live/continuous money shot **at least 5 times** and use the best. Shoot it the FIRST time it works,
  not on Wednesday.
- Keep a `docs/img/shots/` folder with the numbered shot list and the take used for each.
- Two cameras is better than one for hardware: a wide locked-off shot plus a close-up insert.

## Edit rules

- Captions on, then **read them once and correct the technical terms**.
- No copyrighted music. A quiet neutral bed at −24 dB, or none at all. Silence under the relay click.
- Every number that appears on screen must be legible at 720p — Devpost embeds are often small.
- Export 1080p, H.264, ≤100 MB where practical.
- **Time the hardware footage and confirm ≥1:00 (Physical AI).** Write the measured duration into the Devpost copy.
- Watch the finished file once at 1.5× and once at 1.0× muted. If the muted pass still communicates, the captions
  and on-screen text are doing their job.

## Preflight

- [ ] ≤3:00 (target 2:30–2:50), timed from the exported file, not the timeline
- [ ] Public YouTube; link verified in logged-out incognito; embeds on Devpost
- [ ] Captions on and corrected
- [ ] No copyrighted music; no third-party logos used as branding
- [ ] Every number spoken appears identically in the README and the Devpost copy
- [ ] Every statistic has an on-screen source and date
- [ ] Every human quote is attributed with permission
- [ ] The **refusal beat** is present and uncut
- [ ] The **insider insight** is shown before it is said
- [ ] Model tiers and Nebius features named by their real names
- [ ] Limitations spoken aloud, with a number
- [ ] Physical AI: ≥1:00 hardware footage, measured; the veto take continuous; the relay click audible
- [ ] The disclaimer / non-certification statement is spoken
- [ ] A non-teammate watched it once and could answer: what does it do, what is new, what does it refuse to do
