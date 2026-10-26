# Hardware tiers — Reflex

**Decide your tier in ticket D-T01, tonight, from what is physically in hand. Do not order parts.**

The tier determines: which local model can run on-device (E1), how the keep-out volume is detected (E2), how the
hardware interlock is wired (E4), and what the video can honestly claim. Every tier can demonstrate all ten veto
rules — the difference is fidelity, not story.

> **The story does not depend on the tier.** A €40 single-axis pusher with a relay in the power path demonstrates
> "deterministic local veto authority with an auditable ledger and a simulated replay of every refusal" exactly as
> well as a €3,000 arm — and it demonstrates it *more reliably*, which is what actually gets filmed on Wednesday.
> Judges reward a working, honest, well-instrumented small rig far more than an impressive one that misbehaves.

---

## Tier 1 — Jetson + real manipulator (best; only if you already own it)

**You have:** a Jetson (Orin Nano / Orin NX / Xavier NX / Nano), a robot arm or a gantry/linear stage with a
real controller, a depth camera or stereo camera, and a relay or safety-contactor you can wire into the power path.

| Item | Detail |
|---|---|
| Edge compute | Jetson — CUDA available, so a genuinely useful local model runs on-device |
| E1 local model | A small NVIDIA open VLM or an ASR model (Parakeet-class) quantised for Jetson. Publish tokens/s or frames/s, peak memory, and 10-minute thermal behaviour |
| E2 sensing | Depth camera → real 3D keep-out volume occupancy, plus a frame-diff witness. Two independent detectors agreeing is a strong safety argument |
| E4 interlock | Relay or contactor in the actuator power path. Measure switching time and veto-to-stop distance |
| Simulator | In-house swept-volume in 3D, or a real physics engine if you already have one working headless |
| Stretch | Isaac GR00T policy is plausible here (D-T27) |
| Video | The strongest footage available. Still: budget 1:30 of hardware and keep the veto take unbroken |

**Cost if buying:** €800–3,000+. **You cannot buy this in four days.** Only choose Tier 1 if it is already on
your desk tonight.

**Watch out for:** a real arm has far more failure modes (calibration, homing, controller firmware, e-stop
wiring, backlash). Time spent debugging a controller is time not spent on the envelope, the ledger and the video —
which are where the points are.

---

## Tier 2 — Jetson or Pi 5 + single-axis stage / servo rail (recommended target)

**You have:** a Jetson or a Raspberry Pi 5, one servo or stepper on a linear rail or a pan/tilt unit, a webcam or
USB microscope, limit switches, a relay module, and something to push.

| Item | Detail |
|---|---|
| Edge compute | Jetson (CUDA) or Pi 5 (CPU). Both run the pipeline comfortably at 10 Hz |
| E1 local model | Jetson: a small quantised NVIDIA open model. Pi 5: a small quantised model at low throughput, or Parakeet-class ASR for a spoken goal — **measure it and report the real number either way** |
| E2 sensing | Webcam + **frame differencing inside the marked keep-out region**. Cheap, deterministic, explainable in one sentence, and it works. Optionally add a tiny classifier as a second witness |
| E4 interlock | A €5 relay module in the actuator's power path, driven by a GPIO. **Use an electromechanical relay, not a solid-state one — the audible click is worth two seconds of video** |
| Simulator | In-house 2D/2.5D swept-volume (D-T04 default recommendation) |
| Stretch | GR00T unlikely; skip it |
| Video | Excellent. The rail, the taped keep-out volume, the intruder object and the relay are all clearly visible in one locked-off shot |

**Cost if buying:** €120–350. **Still too slow to order.** Choose Tier 2 only if the parts are in hand.

This is the sweet spot: enough fidelity to look like real automation, few enough failure modes to be reliable on
camera, and a Jetson or Pi that can plausibly run a local model.

---

## Tier 3 — €40 minimum viable rig (the floor; fully sufficient)

**You have:** any microcontroller or single-board computer (Arduino, ESP32, Pi Zero 2 W, Pi 3/4/5), one hobby
servo or a small stepper with a driver, a webcam or a phone as a camera, a relay module, some tape, and a small
object to push.

**Bill of materials (indicative, EU prices):**

| Part | Approx. | Notes |
|---|---|---|
| Microcontroller / SBC | €5–60 | Use what you own. A Pi 5 is best; an ESP32 is enough for the actuator + relay path |
| Hobby servo (MG996R-class) or small stepper + driver | €8–20 | A servo on a 3D-printed or cardboard linear pusher is fine |
| Linear rail / drawer slide / extruded aluminium | €0–15 | A drawer slide and a bit of wood works. **Photograph it — a visible hand-built rig reads as authentic, not as cheap** |
| USB webcam or USB microscope | €15–35 | A €20 USB microscope gives superb close-up footage of a keep-out volume |
| Electromechanical relay module (1–2 channel) | €3–6 | **In the actuator power path. Must click audibly** |
| Limit switches / microswitches (2) | €2–4 | Travel limits → V5 |
| Object to push + intruder object | €0 | A wooden block and a second block. Tape the keep-out volume on the bench |
| PSU, wiring, breadboard | €5–15 | Size the PSU for the servo's **stall** current, not its rated current (see the discrepancy note below) |
| **Total** | **€40–170** | Say the real number in the video — it is a credibility signal, not a weakness |

| Item | Detail |
|---|---|
| Edge compute | Whatever you have. If it cannot run a model locally, run the small model on a laptop acting as the "edge" and **say so plainly** — do not imply it is on the microcontroller |
| E1 local model | If the SBC can run a small quantised model, do it and benchmark it. If not: the honest fallback is a tiny on-device classifier for keep-out occupancy (a few hundred lines, runs anywhere), and you state that the large local model runs on the workstation. **Never overclaim where the model runs — a judge who knows Jetson hardware will catch it instantly, and being caught destroys the whole submission** |
| E2 sensing | Frame differencing in the taped region. Add a microswitch or a broken-beam tripwire as an independent physical witness — cheap, and it makes V2 robust |
| E4 interlock | Relay in the servo's power lead. Measure veto-to-stop distance by filming at the highest fps you have and counting frames |
| Simulator | In-house 2D swept-volume, ~200 lines of numpy |
| Stretch | None. Protect the base system |
| Video | Fully sufficient. Lock the camera, light evenly, get the relay close-up |

**What Tier 3 can prove:** all ten veto rules; hard veto authority via a physical interlock; deterministic
decisions (500-replay hash identity); zero network dependency in the envelope; fail-safe behaviour under a
network outage with a strictly-stricter degraded parameter set; an append-only veto ledger that survives an
outage; two-arm simulation replay of every veto from one pinned Sandbox image.

**That is the entire claim.** Tier 3 proves all of it.

---

## Tier 4 — no hardware

**STOP. Switch to Idea A.**

A Physical AI submission with no hardware footage cannot meet the track's requirement of ≥1 minute of video
showing the hardware or modules in use. A simulation-only entry competes in the crowded software field where you
have no advantage, and it forfeits the one thing that made Idea D worth the risk: an unforgeable moat.

Do not spend Sunday building a simulation-only version of Reflex hoping it will scrape into the Physical AI track.
Build Idea A instead, where the moat is a public dataset rather than a piece of hardware you do not have.

---

## Cross-tier notes

### The two discrepancies you will definitely hit (write them into `docs/DISCREPANCIES.md`)
1. **Servo stall current vs datasheet.** A hobby servo's stall current can be 2–4× its rated current, and a
   stalled servo will brown out a shared PSU and reset your microcontroller — which looks exactly like a
   mysterious intermittent failure. **Give the actuator its own PSU, or size for stall, and record what you
   measured.** This is also a safety point: an actuator that can brown out its own controller cannot be trusted
   to stop when told.
2. **Relay switching time vs datasheet.** Datasheet figures are typically for ideal conditions at rated load.
   Measure yours (high-fps camera, or a scope across the coil and the contacts). Your **veto-to-stop latency**
   number is meaningless without it.

Both make excellent, specific Devpost feedback content and both are the kind of detail that signals real hardware
was involved.

### Lighting
Frame differencing is lighting-dependent. Diffuse the light, avoid a window in shot, and **re-run the
false-positive study (D-T24) at the lighting you will film in.** A veto that fires because a cloud passed over
the sun will wreck the take.

### Camera mounting
Lock the camera down. A handheld shot of a safety system reads as amateur. Two cameras is better than one: a wide
locked-off shot of the whole rig, and a close-up on the relay. The relay close-up is a separate insert in the edit.

### What to photograph on Sunday (D-T01)
The whole bench, each part individually, the relay wired into the power path, the taped keep-out volume, and the
rig in motion (a short clip). These photos go into `docs/img/hardware/` and into the README. **A visible,
hand-built rig with a parts bill is a credibility asset** — it says you actually did this, which is the thing
hardware footage exists to prove.

### Sourcing parts in the Netherlands on a Sunday (only relevant if something small is missing)
Electronics components are widely available from EU/online distributors, but **standard weekend/evening delivery
will not get anything to you before the deadline.** If a single small part is missing (a relay module, a servo, a
switch), check whether a local electronics shop, a makerspace, a FabLab, or a university lab in Eindhoven can
supply it today — Eindhoven has an unusually dense electronics ecosystem for exactly this reason. **If it cannot
be in hand tonight, plan without it.**

### Safety
Even a €40 rig moves. Do not put fingers in the swept volume while it is under automatic control; use the intruder
object on a stick or a string for the veto demonstrations, and use a hand only in a take where you have rehearsed
the veto and the velocity is low. **If you film a hand entering the keep-out volume, the velocity limit must be
set well below anything that could injure, and you should say so.** A submission that films an unsafe
demonstration of a safety system will be judged harshly, and deservedly.
