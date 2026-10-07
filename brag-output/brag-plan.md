# Brag plan: UVM Configuration Intelligence (Team Asterix)

**What it is:** a dashboard that reads UVM simulation logs and tells verification engineers which settings make tests fail, which failures are real RTL bugs rather than seed noise, and which config to run next.
**For:** pre-silicon verification teams drowning in regression failures.
**Sets it apart:** determinism fingerprinting separates a real bug (one identical trace across hundreds of seeds) from random noise.
**Most impressive claim (real, from the bundled 50,000-run analysis):** 804 failures, 1 distinct trace, determinism 0.9988 → flagged as a deterministic RTL bug.
**Hook:** a wall of real UVM_ERROR log lines: "50,000 test runs. 12,000 failed." (24.0% failure rate on the 50,000-run sample.)
**Share caption:** see share-copy.txt.

**Tone:** default (punchy, clean). 1920x1080, 30fps, 24s.
**Identity:** the app's own tokens: bg #f5f6f8, text #171a21, accent #4a5fe0, danger #cc352d, success #16884f, purple #7449db; Inter + JetBrains Mono. Dark navy (#0c0f1a) for the hook.

## Storyboard (beats at 120 BPM)

| # | Time | Scene |
|---|---|---|
| 1 | 0.0–3.0 | **Hook.** Real UVM log lines (from `uvm_intel.generate_logs`) scroll fast, red ERROR lines. "50,000 test runs." then "12,000 failed." |
| 2 | 3.0–5.5 | **Reveal.** Logs blur back. "UVM Configuration Intelligence" + "Turns UVM sim logs into root causes." |
| 3 | 5.5–9.0 | **Entry.** Wipe to the app. Upload card (real copy), cursor clicks "Use Bundled Sample", Executive Summary KPI cards count up (50,000 / 24.0% / 0.884). Caption: "Drop in your logs." |
| 4 | 9.0–13.0 | **Highlight 1.** Global SHAP Importance bars grow (lengths taken from the real chart). Caption: "See which settings make tests fail." |
| 5 | 13.0–17.5 | **Highlight 2.** Failure Fingerprints cluster table rows land; c1 PROTOCOL_VIOLATION row lights up, Traces = 1, determinism 0.9988. Caption: "804 failures. One identical trace. A real RTL bug." |
| 6 | 17.5–21.0 | **Highlight 3.** Recommendations: "Found 111 configuration(s) under the 2.0% risk ceiling across 150 trials." + top rows "within ceiling". Caption: "Then the fastest config under 2% risk." |
| 7 | 21.0–24.0 | **Outro.** Asterix logo, title, "Logs in. Root causes out.", Team Asterix · Sandisk Hackathon, repo URL. |

All numbers and UI copy come from the dashboard's real output on the bundled 50,000-run sample (poster screenshots in booth-posters/v3). UI panels are rebuilt in HTML with the app's own CSS tokens and copy. No customer data or secrets appear.

## Sound
Synth track in A minor, 120 BPM: low drone + ticking hats under the hook, riser into the 3.0s drop, then kick/bass/pad/pluck. Effects in key and mixed under: soft click on the button, filtered whooshes on scene changes, a low hit + A chord on the RTL-bug reveal, resolve on the outro.
