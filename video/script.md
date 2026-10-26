# 2:50 demo video — shot list

**Hard limit:** ≤ 3:00. **Target:** 2:50. Physical AI requires **≥ 1:00 of footage of the hardware or key
modules actually operating** (see `docs/SUBMISSION-CHECKLIST.md` §B).

**Rule for this file: every shot below must be filmable with what exists.** Anything not yet built is marked
**[Phase B]** and cannot appear in the submitted cut until it does. An unbacked shot is the fastest way to
lose the panel that scores honesty (`docs/JUDGING-RUBRIC.md` §3).

| Timecode | Shot | What must be on screen | Spoken line |
|---|---|---|---|
| `0:00 – 0:20` | Persona and problem | Kai's cell: pusher, block, taped keep-out volume, relay module. No stock footage | State the pain in the persona's words: *"I can plan a robot's next action in two seconds. I can't tell anyone what I stopped it from doing, or prove the thing that stopped it can't be talked out of it."* |
| `0:20 – 0:50` | The veto, live, one unbroken take | Left: camera. Right: terminal showing intended action → decision → actuator state | "The planner proposes the push. The block is inside the keep-out volume. The envelope vetoes. The relay opens. The actuator has no power." |
| `0:50 – 1:20` | The relay and the ledger **[Phase B]** | Close-up of the relay click; `runs/veto-ledger.jsonl` line landing with rule id, intended action, full rule trace | "Every refusal is written down — including the ones that allowed motion. This is the artifact a client or an insurer asks for." |
| `1:20 – 1:50` | Replay compare **[Phase B]** | Two stills side by side from one pinned sandbox image: `envelope_off` collides, `envelope_on` does not | "Same image, same seed, two arms. This is what the veto prevented." |
| `1:50 – 2:15` | Network cut **[Phase B]** | Pull the cable; mode badge flips NORMAL → DEGRADED; parameter table shows the stricter values | "Cut the network and the cell does not fail open. It switches to stricter limits and keeps operating." |
| `2:15 – 2:35` | What is not done | `LIMITATIONS.md` on screen, with the real numbers (rules implemented, fixtures, measurements) | "Here is what isn't finished, with the count. That's the honest state of the build." |
| `2:35 – 2:50` | Close | Architecture still: cloud proposes, edge decides, ledger proves | "A safety layer that consults the network isn't a safety layer. This one is local, deterministic, and keeps receipts." |

**Do not claim in the voiceover:** a collision-free hardware session, measured veto-to-stop latency, or a
model running on-device — unless the numbers are in the repo and the footage shows them.
