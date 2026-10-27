# D-DEVPOST — submission & video-hosting lock

**Ticket.** Three action items: (1) live-demo badge + link at the top of `README.md`; (2) the Devpost
headline reproduced verbatim, the live Pages URL with judge instructions, and a clearly-marked video
placeholder; (3) `docs/DEVPOST_FEEDBACK.md` verified as the completed writeup for the **$100 Most
Valuable Feedback** award.

## WHAT

| # | File | Change |
|---|---|---|
| 1 | `README.md` | The user's `Live Demo` badge markdown at the very top (line 3) + a one-line "open the live demo" pointer naming frame 41 and the `simulate replay` control |
| 1b | `README.md` | Headline blockquote now reads `1,000 Actions Planned · 420 Vetoes Enforced · 248 Prevented (170 contacts + 78 boundary excursions) · 0 Shipped`; the explanatory paragraph was re-pointed so it no longer claims the banner "keeps the ticket's wording" |
| 2 | `docs/DEVPOST_SUBMISSION.md` | `### The headline` (verbatim string + the 170/78 split), `### For judges — 60 seconds, no install` (4 steps, every number traceable to the bundle), `TODO_VERIFY(hosting)` video placeholder |
| 2b | `docs/DEVPOST_SUBMISSION.md` | New honest-list row: the video exists but is **not hosted**; the form field is a placeholder |
| 3 | `docs/DEVPOST_FEEDBACK.md` | Rewritten as platform feedback: 7 sections, 2,443 words, 5 documentation gaps, 2 self-inflicted breakages, 4 feature requests, a numbers table in which every cloud row says **NOT MEASURED** |
| 3b | `docs/DEVPOST_FORM_NOTES.md` | New file. The six Devpost-*form* observations that used to live in `DEVPOST_FEEDBACK.md`, preserved verbatim with a re-titled H1 and current state |

## VERIFIED

Real output, this session:

```
$ cd backend && uv run --extra dev pytest tests/ -q
430 passed, 1 skipped in 17.31s        # fresh state: bundle absent, so test_static_replay skips

$ make check
431 passed in 16.43s
make check: PASS — lint, types, contracts, taxonomy, calibration, fixtures and tests are green

$ make pages-check
  PASS  bundle is complete                         100 frames · 100 decisions
  PASS  every decision has both replay arms        100 comparisons
  PASS  the veto is where the timeline says it is  frame 40 · t=4.0 s · V2_KEEP_OUT_OCCUPIED
  PASS  the tool tip advances 10 → 70 mm           10.0 → 70.0 mm in 4.0 s
  PASS  the interlock latches                      59 later proposals refused
  PASS  nothing collided under the envelope        0 of 100 shipped arms collided
  PASS  the refusal prevented a collision          off: keep_out_volume at (150.0, 0.0) mm · on: completed
STATIC REPLAY CHECK PASS — 7 checks on the published bundle
```

**On the test count.** The user's figure (430) and the previously reported figure (431) are both
correct and describe different states: the bundle-dependent test in `backend/tests/test_static_replay.py`
**skips** when `frontend/public/replay/bundle.json` is absent, and that directory is gitignored
(`.gitignore:70`). A fresh clone therefore reports **430 passed, 1 skipped**; after `make pages-data` it
reports **431**. Both documents now say so explicitly instead of picking one number.

## Facts checked rather than assumed

| Claim | How it was checked |
|---|---|
| Page opens on the veto frame | `initialStep()` (`frontend/src/staticReplay.ts:142-148`) returns `firstVetoIndex(bundle)` when no `?step=`/`?autoplay=` is present; live page showed `frame 41 / 100 · t = 4.0 s` |
| "59 later proposals refused" | `make pages-check` → `PASS the interlock latches 59 later proposals refused` |
| "off collides at (150.0, 0.0) mm" | `bundle["replays"][id]["envelope_off"]["collision"]` = `{contact_point:{x:150.0,y:0.0}, with:"keep_out_volume"}`; exporter PASS line |
| The status chip text | `frontend/src/App.tsx:838-841` → `replay/bundle.json · recorded, not live`. An earlier draft of this work said "RECORDED SESSION" — **a phrase I had invented**; it was replaced with the string the code actually renders |
| "envelope on stops at 0.0 mm travelled" | True but imprecise: `envelope_on` reports `outcome: "completed"`, `distance_mm: 0.0`, note *"the envelope shipped no action; the arm did not move"*. Reworded to "ships nothing — the arm does not move" |
| Video size/duration | `docs/media/reflex-demo.json` → `runtime_s.mp4 = 164.77`, `files.mp4.bytes = 10 668 327` (= 10.7 MB = 10.2 MiB; the user's "10.6 MB" is the same file, decimal MB) |
| Zero Token Factory calls | `LIMITATIONS.md:99`; `runs/ledger.jsonl` does not exist (`ls` → No such file) |

## COSTS

No new dependencies. `uv` was reinstalled into the sandbox (`pip install uv`) only to run the existing
`make` targets — it is not added to the project. Model IDs, schemas and `frontend/src/tokens.css` were not
touched.

## TODO_VERIFY

1. **`TODO_VERIFY(hosting)`** — `docs/DEVPOST_SUBMISSION.md:4,114`. The video has no public URL.
   `https://youtu.be/<VIDEO_ID>` is a placeholder in backticks (not a link). It must be replaced with a
   real upload before the form is submitted; a 10.7 MB / 2:45 file is within YouTube's and Loom's limits,
   but **no upload was attempted**, so nothing about either service is asserted.
2. **Doc URLs in the feedback** — `docs.tokenfactory.nebius.com/...` was unreachable from this sandbox.
   The feedback says so in its own preflight and does not present those pages as read. If the Devpost
   form requires verified links, they must be checked by hand before sending.
3. **Contact detail** — the feedback signs with the GitHub handle only; add an email if follow-up is
   wanted.

## DEVIATIONS

1. **The feedback file was replaced, not appended to.** The award asks for feedback on Nebius Token
   Factory / AI Cloud / NVIDIA tools; the file held feedback on the *Devpost form*. Rather than delete
   real work, the six sections moved verbatim to `docs/DEVPOST_FORM_NOTES.md`, and the feedback doc
   ends with a pointer to it.
2. **No measured platform metrics were invented.** The template asks for spend, tokens, p50/p95 and
   sandbox timings. This build made **zero** calls, so §4 lists those rows as **NOT MEASURED** and names
   the ledger field that would fill each one. A feedback document with plausible percentiles but no key
   would be fabrication, and it would contradict `LIMITATIONS.md` in the same submission.
3. **The headline paraphrase was fixed rather than left.** `README.md` previously said the banner "keeps
   the ticket's wording" while the banner said something slightly different; since the banner now carries
   the exact requested string, that sentence was corrected to match.
4. **`docs/DEVPOST_FORM_NOTES.md` is a new file** (scope: one file beyond the three named in the ticket).
   The alternative was deleting 106 lines of prior analysis.

## NOT_DONE

- Video not uploaded; no URL exists.
- No Devpost form submitted — the form is a manual step, and `SUBMISSION-CHECKLIST.md` still tracks it.
- The feedback has no measured platform numbers (0 calls), by necessity rather than by omission.
- `make demo-check` was not re-run: nothing in this diff touches the demo path, and `make check` +
  `make pages-check` cover the changed files.

## NEXT

1. Upload `docs/media/reflex-demo.mp4` (or `.webm`) to YouTube/Loom, paste the URL over
   `https://youtu.be/<VIDEO_ID>` in `docs/DEVPOST_SUBMISSION.md`, drop the `TODO_VERIFY(hosting)` marker.
2. Submit, pasting: the headline string, the live Pages URL, the video URL, and the body of
   `docs/DEVPOST_FEEDBACK.md` for the feedback award.
3. If a Token Factory key becomes available before the deadline: one `UltraPlanner.plan(...)` call
   populates `runs/ledger.jsonl` and turns the `NOT MEASURED` rows into real numbers — the one change
   that would most improve the feedback entry.
