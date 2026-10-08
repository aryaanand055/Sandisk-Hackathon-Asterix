# Team Asterix: Jury Pitch Script (7 to 8 min)

**Pre-Verification Silicon Testing Analytics.** *Every failure, explained. Every next run, chosen.*

---

## 0. Running order at a glance

| # | Speaker | Time | Covers | Poster in hand | On screen |
|---|---|---|---|---|---|
| 1 | **Josana** | 0:00 – 1:45 | Hook, problem, market need, architecture | **01 The Problem**, **02 The Engine** | Upload page (bundled sample already loaded) |
| 2 | **Niyathi** | 1:45 – 3:45 | *"Why did it fail?"* Executive Summary, Failure Fingerprints, AI Copilot | **04 The Product** | Live dashboard |
| 3 | **Arya** | 3:45 – 5:45 | *"What changed, and what runs next?"* Config Diff, Tradeoff, Recommendations, Run Explorer, Export, real simulator logs | **05 The Insights** | Live dashboard |
| 4 | **Joel** | 5:45 – 7:45 | How the logs are made, the NAND design, the "7 hidden bugs" reveal, business value for SanDisk, close | **03 The Proof**, **06 The Impact** | Generate logs page, then back to the summary |

**Target: 7:30. That leaves 30 seconds of slack under the 8-minute cap.** Spoken pace is about 130 words a minute, so each part below is about 230 to 260 words.

**The story in one line:** *We don't find failures, everyone can do that. We **explain** them, and we tell you **what to run next**.*

**The narrative trick:** Niyathi and Arya show what the dashboard *finds*. Joel then reveals that we **planted** those exact bugs ourselves, and the tool found all 7 without being told. Save the reveal for Joel; nobody says "7 bugs found" before him.

---

## 1. JOSANA: Problem and System Architecture (0:00 – 1:45)

**Poster: 01 The Problem → switch to 02 The Engine at "So we built…"**

> Good morning. We're Team Asterix, and our project is **Pre-Verification Silicon Testing Analytics**.
>
> Before a chip like a SanDisk flash controller goes to silicon, it's verified in simulation. The same tests run across **thousands of configurations and random seeds**. One regression can produce **thousands of runs, millions of log lines**, and a big pile of failures.
>
> Finding the failures is easy. The hard part is the question every engineer asks next: **why did it fail?** Which setting caused it? Is it a real RTL bug, or just bad luck with a random seed?
>
> This matters commercially. According to the Siemens–Wilson Research verification study, **49% of a chip designer's time goes into verification**, **debugging is the number-one time sink**, and demand for verification engineers is growing **2.3 times faster** than for designers. Verification time is what holds back tape-out, and it's the most expensive time in the project.
>
> *(point at the bottom of poster 1)* The brief gave us eight questions. We grouped them into three: **Why did it fail? What changed? What should run next?**
>
> *(switch to poster 2)* So we built one engine: **one upload in, one explained report out.**
>
> You give it UVM simulation logs or CSV tables. **Ingestion** parses and joins them into one table of runs and one table of errors. On our sample, that's **a million log lines parsed in about 2 seconds**.
>
> Then five analysis stages run: a **risk model** with LightGBM and SHAP, **failure fingerprinting** with TF-IDF and DBSCAN, a **config diff** that finds each failure's nearest passing twin, a **Pareto tradeoff** of speed against risk, and a **recommender** using Optuna that searches for the fastest config under a 2% risk cap.
>
> Everything goes into one JSON report, served by FastAPI to a React dashboard with **eight tabs and an AI copilot**. Niyathi will show you what it says.

### Hints for Josana
- **Open strong and slow.** The first 10 seconds set the tone. Make eye contact, don't read.
- **Remember three numbers:** **49%** (verification time), **#1** (debugging), **2.3×** (demand growth).
- **The key sentence:** *"Finding failures is easy. Explaining them is the problem."* Pause after it.
- **On the architecture, trace the poster with your finger** left to right: Inputs → Ingestion → 5 stages → Serve → Dashboard. Say the stage **names**, not the algorithms, if you're short on time. The algorithms are on the poster.
- If the jury is more business-minded, cut the algorithm names and say: *"five stages that predict, group, compare, trade off and recommend."*
- **Handoff:** *"Niyathi will show you what it says."* Then step aside so the screen is visible.

---

## 2. NIYATHI: Dashboard Part 1, "Why did it fail?" (1:45 – 3:45)

**Poster: 04 The Product. Screen: Executive Summary tab (Arya drives the mouse)**

> This is the live dashboard, running on our **50,000-run** NAND flash sample. Every chart has a one-line takeaway and a "how to read" note, so a manager can read it, not just the engineer who built it.
>
> **Executive Summary.** Top left, pass/fail: **24% of runs fail, that's 12,020 failures.** Too many to triage by hand.
>
> Failure modes: **51% of all failures are just two tags**, data mismatch and timeout. So we know *how* runs fail. Now, *why?*
>
> This is the most important chart: **global SHAP importance**. Our risk model learns from **configuration settings only**, never from the outcome, so it can't cheat. It says **29% of predicted risk comes from test mode**, and clock speed is next at **14%**. That points straight at the settings to look at.
>
> Because it learns from settings, it can **predict failure before a test even runs**. Risk bands: **7,557 runs, 15%, are high or critical risk.** Triage those first. And the ROC curve shows it's reliable: **AUC 0.88**, catching **97% of failures** at the balanced point.
>
> *(click Failure Fingerprints)* Next question: **is a failure a real bug or just noise?** We mask out addresses and numbers so every error becomes a template, then cluster them. Each dot is an error type. This one is **protocol violation: one identical trace across 804 different seeds.** Random noise changes with the seed. This doesn't. **It's a deterministic RTL bug, so file it first.** The other error types change with every seed.
>
> *(click AI Copilot)* And to ask anything in plain English, there's the **AI Copilot**, built on Google Gemini. *(type: "Which setting should I fix first?")* It answers using the analysis.
>
> Arya will show you what to change next.

### Hints for Niyathi
- **Your theme is "Why did it fail?"** Every chart answers that question.
- **Remember five numbers:** **24%** fail · **29%** test mode · **0.88** AUC / **97%** caught · **804 seeds, 1 trace**.
- **Use the chart takeaways.** Each chart in the app already states its headline, so if you blank, read the takeaway and move on.
- **The "can't cheat" line** answers the judges' leakage question before they ask it. Say it confidently.
- **Fingerprints is your wow moment.** Point at the big dot and slow down on *"804 seeds, one trace."*
- **Copilot:** have the question **typed or copy-ready** beforehand. If the API is slow, don't wait. Say *"it answers in plain English, and it still gives a rule-based summary with no API key"* and move on.
- **Don't say "we found 7 bugs."** That's Joel's reveal.
- **Handoff:** *"Arya will show you what to change next,"* then swap the mouse with Arya.

---

## 3. ARYA: Dashboard Part 2, "What changed, and what runs next?" (3:45 – 5:45)

**Poster: 05 The Insights. Screen: Config Diff (Niyathi drives the mouse)**

> Knowing the cause is half the job. An engineer also needs to know **what to change**, and a manager needs to know **what to run next**.
>
> **Config Diff.** For every failing run, we find its **nearest passing twin**: the most similar run that passed. The settings that differ are the suspects. Across **1,600 pairs**, **46% differ in clock speed**, so that's the first knob to check. *(click a pair)* You can also open two runs side by side and diff their logs line by line.
>
> *(click Tradeoff Matrix)* Engineers don't only want safe, they want **fast and safe**. Each dot is one of **320 configurations**, plotted by throughput against predicted risk. The blue line is the **Pareto frontier**, the **15 configs that nothing beats on both**. The sweet spot is **47.6 Mbps at 3.4% risk.** Doubling the speed to 94.7 costs **50% risk**. So it shows exactly what a little more speed costs in risk.
>
> *(click Recommendations)* Then we go beyond configs we've already run. The **recommender** uses Optuna to search for the fastest config that keeps predicted risk **under 2%**. Of **150 trials, 111 stayed under the cap**, and the best predicts **381 Mbps at 1.98% risk**. That's what you put in tomorrow's regression.
>
> *(click Run Explorer, then All Details, quickly)* Every run is searchable here, and All Details shows the full numbers, including failure rate and lift for every setting. *(click Export PDF)* And one click exports the whole analysis as a **PDF report** to share with your manager.
>
> And this isn't only for our sample. The parser already reads **real QuestaSim, VCS and Xcelium transcripts**: test name, seed, plusargs, UVM errors and the pass/fail verdict.
>
> So how do we know the answers are *right*? Joel.

### Hints for Arya
- **Your theme is "action."** Niyathi explained *why*. You say *what to do about it*.
- **Remember five numbers:** **46%** clock speed · **320 configs / 15 on the frontier** · **47.6 Mbps at 3.4%** · **111 of 150** · **381 Mbps at 1.98%**.
- **Tradeoff is the most business-friendly chart.** Say *"what a little more speed costs in risk"* while looking at the judges, not the screen.
- **Run Explorer, All Details and Export are a 15-second fly-by.** Don't explain them, just show they exist. Cut them first if you're behind on time.
- **The real-simulator-log line** answers *"does this work on real data?"* before it's asked. Only say it if you've tested a real transcript upload on the demo machine.
- **Handoff:** end on the question, *"So how do we know the answers are right?"*, and turn to Joel. It gives his reveal a strong entry.

---

## 4. JOEL: Log Generation, NAND Design, Proof, and Business (5:45 – 7:45)

**Poster: 03 The Proof → switch to 06 The Impact at "So what does this mean for SanDisk?"**

> Real regression logs have one problem: **no answer key**. You can never prove the tool found the *true* cause. So we built our own, with a hidden answer.
>
> **Our design under test is a NAND flash storage controller**, SanDisk's core product. **Eight tests**: program, read, write, mixed read-write, erase-suspend, garbage collection, read-disturb and power cycle. They're varied across **11 settings**, such as channels, planes, ECC, cache policy, clock and queue depth, plus **2 sensors**, temperature and voltage.
>
> *(point at "How a run is made")* Each run is made in five steps. **One shared log format**, used by both the generator and the parser so they can't drift apart. **Sample the settings.** **Plant 7 bugs**, each of which raises the failure odds. **Compute pass or fail** from that run's settings. **Write realistic UVM logs** with config, UVM errors, metrics and a pass/fail banner. That gives **50,000 runs, 1.02 million log lines, 56 MB**. Anyone can build their own test set from the **Generate logs** page in the dashboard.
>
> And here's the reveal. **Everything you just saw, we planted.** Test mode, the top SHAP driver, is our rule R2. The protocol-violation cluster across 804 seeds is R5, a deliberate RTL bug that prints the same trace every time. **We hid 7 bugs, and the dashboard found all 7 blind.**
>
> *(switch to poster 6)* So what does this mean for SanDisk? It fits every team that runs thousands of configs and seeds: **flash controller verification, SSD firmware, NAND reliability** across temperature, voltage and ECC, and **NVMe/PCIe**. The value is simple: **engineers stop triaging and start fixing**, real RTL bugs get filed first, **compute stops being wasted re-running seed noise**, and the next regression is planned from data, not guesswork. That saves verification time, the biggest cost before tape-out.
>
> And it's not limited to chips. Software CI, cloud configs, automotive and manufacturing yield all have the same problem.
>
> Next: trends across nightly runs, a CI gate that blocks new real bugs, and auto-triage to owners.
>
> **Every failure, explained. Every next run, chosen.** Thank you.

### Hints for Joel
- **You have the two strongest moments:** the **reveal** and the **closing line**. Slow down for both.
- **The "why synthetic?" answer** is your first line. Make it sound like a deliberate design choice, because it is one: *"real logs have no answer key."*
- **Remember these numbers:** **8 tests · 11 settings + 2 sensors · 7 bugs · 50,000 runs · 1.02M lines · 56 MB**.
- **For the reveal, connect it back to what they saw:** "test mode = R2", "804 seeds = R5". That callback is what makes it land. Point at R2 and R5 on poster 3.
- **Business section:** say "SanDisk" by name, and use the verbs *triage, file, rerun, plan*. Those are the four concrete savings.
- **Optional, if you have 10 seconds spare:** flash the *Generate logs* page on screen. Otherwise just mention it.
- **Last line:** say *"Every failure, explained. Every next run, chosen."* Pause. *"Thank you."* Then stop talking and let them ask questions.

---

## 5. Live demo setup checklist (do this 10 minutes before)

1. Start the backend and frontend. **Restart the backend by hand** if you've touched `backend/main.py` (uvicorn `--reload` can hang on Windows).
2. Click **Use bundled sample** and let the analysis **finish before you walk up**. Never run the analysis live in front of the jury.
3. Have the dashboard on the **Executive Summary** tab and zoomed so the back row can read it (Ctrl + to about 125%).
4. **AI Copilot:** check the Gemini key works, and run your question once beforehand so you know the answer is good.
5. Keep a **second browser tab** with the same finished analysis as a backup if the first one breaks.
6. **Backup of the backup:** keep the posters (and `UVM_Configuration_Intelligence_Summary.pdf`) ready. If the site dies, present straight from the posters. Every number in this script is on them.
7. **Mouse rule:** the speaker talks, a teammate clicks. Arya drives for Niyathi, Niyathi drives for Arya. Agree on the click order beforehand.
8. **Rehearse with a timer at least twice.** If you run over, cut in this order: Run Explorer/All Details fly-by → the beyond-chips list → algorithm names in the architecture.

---

## 6. Likely jury questions, and who answers

| Question | Who | Answer |
|---|---|---|
| *Isn't synthetic data cheating?* | Joel | It's the opposite. Real logs have no answer key, so you can't prove anything. Ours does, so every insight can be checked. The parser also reads real Questa/VCS/Xcelium transcripts. |
| *Does the model leak the answer?* | Niyathi | No. It trains on configuration settings only. Outcome columns like error type, runtime, throughput and seed are excluded. That's why it can predict *before* a run. |
| *How do you tell a real bug from noise?* | Niyathi | Determinism: a real bug gives the **same** trace on every seed. 804 seeds and 1 trace is a bug. A different trace on every seed is noise. |
| *Why is the recommendation (381 Mbps) higher than anything on the Pareto chart (94.7)?* | Arya | The Pareto chart covers configs we've **already run**. The recommender searches the **whole space**, including combinations never tried, using a throughput model trained on passing runs. It's a prediction to validate in the next regression. |
| *How fast/scalable is it?* | Josana | About 1M log lines parse in ~2 s. The upload limit is 512 MB. Each analysis stage runs on its own, so one failing stage doesn't break the report. |
| *Is chip IP sent to Google?* | Arya | Only a condensed summary goes to the copilot, and only if a key is set. Everything else runs locally, and the copilot falls back to a rule-based answer without a key. It could be swapped for an on-prem model. |
| *What's the ROI for SanDisk?* | Joel | Less engineer time on triage (debugging is the #1 cost), real bugs filed earlier, less compute spent re-running seed noise, and faster regression planning. All of that shortens time to tape-out. |
| *What's next?* | Joel | Trends across nightly runs, a CI gate on new real bugs, auto-insight cards, then coverage-aware picks and auto-triage to owners. |

---

## 7. Full script, continuous (for read-through rehearsals)

Read sections 1 → 2 → 3 → 4 above in order, without the hints. Total about 1,000 words, about 7:30 at a calm pace.
