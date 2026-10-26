# LIMITATIONS.template.md — honesty as a scoring strategy

**Used by:** A-T37 / B-T37 / C-T37 / D-T33. Copy, fill every `<…>`, delete this header.

> **Why this file exists.** In the judges' own video, the submissions that landed best were the ones that were
> candid about what they had *not* done, and the ones that got picked apart were the ones whose claims outran
> their evidence. A precise limitations file does three things: it removes the judge's favourite attack (they
> cannot find a gap you already named), it demonstrates domain understanding (only someone who understands the
> problem knows where it is hard), and it makes every other claim in your submission more believable.
>
> **The standard this file must meet:** a sceptical expert reads it and finds no unbacked sentence, and finds
> every gap they would have raised already listed with a number attached.
>
> **The rule for every bullet:** `what is limited` + `the number` + `why it is that way` + `what would fix it`.
> A limitation without a number is an apology. A limitation with a number is an engineering finding.

---

## The file, in order

```markdown
# Limitations — <Project Name>

<One paragraph, plain, no hedging. State the single biggest limitation and the single biggest risk of
misinterpretation. Example: "This is a screening tool, not a compliance authority. It reports what it could
verify against public sources at a point in time; it does not and cannot tell you that a product is legal to
sell.">

**Read this before you trust any number in this repository.**

---

## 1. What this is not

<3–6 bullets. Each one names a thing a reader might assume and denies it explicitly. This is where your
disclaimer lives in full. Examples by idea:>
- <A: "This is not legal advice and not a compliance certification. A COMPLIANT verdict means 'no rule in our
  table fired', not 'this product may lawfully be sold'.">
- <B: "Not affiliated with, endorsed by, or certified against IPC-A-610 or J-STD-001. Thresholds are ours.">
- <C: "We report the published official position, not a prediction. This is not a substitute for a formal
  application or a grid operator's determination.">
- <D: "A research prototype, not a certified safety system. It does not constitute compliance with ISO 10218,
  ISO/TS 15066, the Machinery Regulation, or any other standard.">

## 2. Coverage — what we did and did not handle

| Dimension | Covered | **Not covered** |
|---|---|---|
| <categories / joint types / regions / rule types / hazards> | <n, named> | <n, named — name them, do not say "others"> |

<Be specific. "We cover 3 product categories out of the ~30 in the Safety Gate taxonomy" is useful. "We cover a
subset" is not. **A judge who spots an unnamed gap assumes there are more; a judge who reads a named gap assumes
you know your system.**>

## 3. Evaluation — what we measured, and what we could not

| Metric | Value | n | Caveat |
|---|---|---|---|
| <accuracy / precision / recall / date-support rate / veto-to-stop latency> | <value> | <n> | <the honest caveat> |
| <per-class or per-code breakdown> | … | … | <which classes are INSUFFICIENT (n<5) and therefore have NO published number> |

- **Test-set size:** <n>. <Target was <n>; we reached <n>. The consequence of the shortfall is <specific>.>
- **Labelling:** <n> labelers, <blind?>. **Cohen's kappa = <value>** (<interpretation>). <n> disagreements,
  <n> adjudicated, notes in <path>. <If kappa is low, say why — low kappa with an explanation is a finding.>
- **What we could not measure:** <e.g. real-world false-accept cost, long-term drift, a class we had no examples
  of>. <Why, and what it would take.>
- **Known biases in the data:** <e.g. self-photographed boards are cleaner than production; a sweep that abstains
  on areas with no machine-readable register is not reporting a negative there; a control sample that was too
  small>.

## 4. The things that will make this wrong in the real world

<The most valuable section. 4–8 concrete failure cases, each with a screenshot/still/photo and the reason code.
These must be REAL cases you actually hit, not hypotheticals.>

| # | What went wrong | Screenshot | Why | What we did about it |
|---|---|---|---|---|
| 1 | <e.g. a listing in a language the extractor handled badly> | <path> | <cause> | <mitigation or abstention> |
| 2 | <e.g. a shiny joint confused the segmentation> | <path> | <cause> | <…> |
| 3 | <e.g. a publisher changed its URL and the corpus went stale> | <path> | <cause> | <…> |
| 4 | <e.g. a false-positive veto fired because a cloud moved the lighting> | <path> | <cause> | <…> |

## 5. Abstention — how often it refuses, and whether it refuses for the right reasons

- **Abstention rate:** <n>% of <n> cases.
- **Abstention appropriateness:** of those, <n>% were on inputs that humans also judged unusable or undecidable.
  <The remaining <n>% are over-cautious; here is the breakdown by reason code.>
- **By reason:** <table of reason code → count>.
- **What abstention costs the user:** <e.g. they must call the operator / re-shoot the photo / check manually>.
  <This is a real cost and it should be stated, not buried.>

## 6. Dependencies that can break

| Dependency | Failure mode | Detection | Behaviour when it fails |
|---|---|---|---|
| <a publisher's URL / an API / a dataset / a model endpoint> | <rots, rate-limits, changes schema, goes down> | <how you'd know> | <degrades to snapshot? abstains? errors?> |
| <Tavily> | unreachable | per-call | <the answer is labelled "currency check unavailable — corpus snapshot from <date>" and may not claim to be current> |
| <the demo host / credits> | credits exhausted, host down | uptime ping | <what a judge sees in December> |

<For any project that depends on live third-party data: state explicitly what the demo does when that data is
unreachable, and confirm that you tested it. "We tested the demo with all external publishers blocked and it
still returns a full, correctly-cited answer from the snapshot" is worth more than any feature.>

## 7. Cost and latency — the real numbers

- Total for the eval: **$<x>** (<n> runs). Per unit: **$<y>**.
- <n> text tokens, **<n> image tokens reported separately** <(image tokens dominate cost in any vision project;
  reporting them together hides the truth)>.
- All-Ultra counterfactual: **$<z>** (<n>× more). Cache-hit rate: <n>%.
- Latency: p50 <n> ms, p95 <n> ms <— split edge vs cloud if there is an edge>.
- <What gets expensive at 100× scale, and what you would change first.>

## 8. Assumptions we made that could be wrong

<4–8 bullets. Each: the assumption, why you made it, and what happens if it is false. This is where a
sceptical judge's questions get answered before they ask them.>
- <e.g. "We assume the extracted statutory quotes are accurate. They are checked by substring match against the
  source document, but the SOURCE SELECTION was ours — if we picked the wrong article, the match proves nothing.">
- <e.g. "We assume a printed A4 target at 210 mm. If a user prints without 'actual size', every measurement is
  scaled wrong and the calibration silently passes. Mitigation: <…>. Residual risk: <…>.">
- <e.g. "We assume the planner is adversarial-ish but not malicious. A deliberately crafted proposal could
  <…>. We tested <n> such cases.">

## 9. Things we cut, and why

| Cut | Why | What it would take |
|---|---|---|
| <feature> | <time / risk / not in service of the hook> | <n hours / n days> |
| <feature> | <…> | <…> |

<Cutting for a reason reads as judgement. Cutting silently reads as incompleteness.>

## 10. Accessibility

- Audited with <tool>: **<n> critical / <n> serious violations** (<0/0 is the target; if not zero, list them>).
- Keyboard-only: <can a full run be completed? tested by whom?>.
- Colour: <all outcome/verdict states distinguishable in greyscale and under deuteranopia simulation — attach the
  screenshots>. Colour is never the only signal.
- Screen reader: <what works, what does not>.
- **Not done:** <e.g. full WCAG 2.2 AA conformance, live captioning, a braille/high-contrast theme>. <What it
  would take, and that it is in Next Steps.>

## 11. Legal, ethical, safety

- <Data licences: what is redistributed, what is fetched at build time, what could not be used and why.>
- <Third-party marks: named as text citations only; no logos used as branding; no implication of endorsement.>
- <Personal data: what is collected (ideally nothing), what is logged, how long it is retained.>
- <Misuse: how this could be used to harm, and what you did about it. For a safety-adjacent project this is
  mandatory — e.g. "a REJECT verdict could be used to scrap good boards; the report says explicitly that it is a
  screening signal requiring human confirmation.">
- <Safety: for hardware, what the rig can and cannot injure, what was tested, what was not — including whether
  you tested a failure of the safety component itself. If you did not, say so.>

## 12. What we would do with two more weeks

<4–6 items, ranked, each with the effort and the expected payoff. This is the section that turns a limitation
into an ambition, and it is the honest version of a roadmap.>
1. <item> — <n days> — <what it would change>
2. …

---

**Last updated:** <date> · **By:** <name> · **Numbers verified against:** `runs/reports/<…>` on <date>
```

---

## Preflight

- [ ] Every bullet has a number, a named cause, or a file path — no bare adjectives
- [ ] ≥4 **real** failure cases with screenshots, not hypotheticals
- [ ] The coverage table **names** what is not covered
- [ ] Classes/codes with n<5 are flagged INSUFFICIENT and have no published accuracy
- [ ] Kappa reported even if it is low, with an interpretation
- [ ] Abstention rate **and** abstention appropriateness both reported
- [ ] The "dependencies that can break" table confirms you tested the offline/degraded path
- [ ] Image tokens reported separately from text tokens (vision projects)
- [ ] The §1 "what this is not" list contains your full disclaimer
- [ ] Accessibility section states what was audited, what passed, and what was **not** done
- [ ] A sceptical read-aloud finds no unbacked sentence
- [ ] Every number matches the README and the Devpost copy exactly
