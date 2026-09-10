/**
 * UVM Configuration Intelligence — project presentation generator.
 *
 * Run:  node build_deck.js
 * Out:  UVM_Configuration_Intelligence.pptx
 */

const pptxgen = require("pptxgenjs");

// ── Design system ──────────────────────────────────────────────────────────
const INK = "10151C";      // near-black graphite
const PANEL = "1B2530";    // dark panel
const SLATE = "3A4757";    // body text on light
const MUTED = "76838F";    // captions
const LINE = "E3E9EF";     // hairline borders
const CARD = "F7F9FB";     // card fill
const WHITE = "FFFFFF";
const AMBER = "F5A524";    // accent (on dark)
const AMBER_D = "A86B12";  // accent text (on light)
const TEAL = "1FB6A6";     // pass / good
const CRIMSON = "E5484D";  // fail / risk
const PH_FILL = "EEF2F6";  // screenshot placeholder fill
const PH_LINE = "B4C0CC";

const F_HEAD = "Cambria";
const F_BODY = "Calibri";
const F_MONO = "Courier New";

const W = 13.333, H = 7.5, M = 0.62;
const CW = W - 2 * M; // 12.093

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "Team Asterix";
pres.company = "SanDisk Hackathon";
pres.title = "UVM Configuration Intelligence";

let pageNo = 0;

const shadow = (o = {}) => ({
  type: "outer", color: "8A96A3", blur: 10, offset: 2, angle: 90,
  opacity: 0.16, ...o,
});

function footer(s, dark) {
  pageNo += 1;
  const c = dark ? "5A6875" : MUTED;
  s.addText("UVM Configuration Intelligence  ·  Team Asterix", {
    x: M, y: 6.92, w: 6, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F_BODY, fontSize: 9, color: c, align: "left",
  });
  s.addText(String(pageNo).padStart(2, "0"), {
    x: W - M - 1.2, y: 6.92, w: 1.2, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F_BODY, fontSize: 9, color: c, align: "right", bold: true,
  });
}

/** Light content slide with kicker + title. Returns the slide. */
function lightSlide(kicker, title, sub) {
  const s = pres.addSlide();
  s.background = { color: WHITE };
  s.addText(kicker.toUpperCase(), {
    x: M, y: 0.40, w: CW, h: 0.26, isTextBox: true, margin: 0,
    fontFace: F_BODY, fontSize: 10.5, bold: true, color: AMBER_D, charSpacing: 2.2,
  });
  s.addText(title, {
    x: M, y: 0.66, w: CW, h: 0.62, isTextBox: true, margin: 0,
    fontFace: F_HEAD, fontSize: 33, bold: true, color: INK,
  });
  if (sub) {
    s.addText(sub, {
      x: M, y: 1.30, w: CW - 0.2, h: 0.34, isTextBox: true, margin: 0,
      fontFace: F_BODY, fontSize: 13, color: MUTED,
    });
  }
  footer(s, false);
  return s;
}

/** Dark content slide. */
function darkSlide(kicker, title, sub) {
  const s = pres.addSlide();
  s.background = { color: INK };
  s.addText(kicker.toUpperCase(), {
    x: M, y: 0.40, w: CW, h: 0.26, isTextBox: true, margin: 0,
    fontFace: F_BODY, fontSize: 10.5, bold: true, color: AMBER, charSpacing: 2.2,
  });
  s.addText(title, {
    x: M, y: 0.66, w: CW, h: 0.62, isTextBox: true, margin: 0,
    fontFace: F_HEAD, fontSize: 33, bold: true, color: WHITE,
  });
  if (sub) {
    s.addText(sub, {
      x: M, y: 1.30, w: CW - 0.2, h: 0.34, isTextBox: true, margin: 0,
      fontFace: F_BODY, fontSize: 13, color: "9AA7B4",
    });
  }
  footer(s, true);
  return s;
}

/** Card container. */
function card(s, x, y, w, h, opts = {}) {
  s.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.06,
    fill: { color: opts.fill || CARD },
    line: { color: opts.line || LINE, width: 1 },
    shadow: shadow(opts.shadow || {}),
  });
}

/** Small square chip carrying a number or short label — the deck's motif. */
function chip(s, x, y, label, color = AMBER, txtColor = INK, size = 0.36) {
  s.addShape(pres.ShapeType.roundRect, {
    x, y, w: size, h: size, rectRadius: 0.22,
    fill: { color }, line: { color, width: 0 },
  });
  s.addText(label, {
    x, y, w: size, h: size, isTextBox: true, margin: 0,
    fontFace: F_BODY, fontSize: 12.5, bold: true, color: txtColor,
    align: "center", valign: "middle",
  });
}

/** Screenshot placeholder with dashed frame. */
function placeholder(s, x, y, w, h, label, hint) {
  s.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.03,
    fill: { color: PH_FILL },
    line: { color: PH_LINE, width: 1.5, dashType: "dash" },
  });
  s.addText("INSERT SCREENSHOT", {
    x, y: y + h / 2 - 0.42, w, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F_BODY, fontSize: 12, bold: true, color: "8С".replace("С", "8") + "94A0".slice(0, 4),
    align: "center", charSpacing: 2,
  });
  s.addText(label, {
    x: x + 0.2, y: y + h / 2 - 0.08, w: w - 0.4, h: 0.34, isTextBox: true, margin: 0,
    fontFace: F_BODY, fontSize: 13.5, bold: true, color: SLATE, align: "center",
  });
  if (hint) {
    s.addText(hint, {
      x: x + 0.25, y: y + h / 2 + 0.28, w: w - 0.5, h: 0.36, isTextBox: true, margin: 0,
      fontFace: F_BODY, fontSize: 10.5, color: MUTED, align: "center",
    });
  }
}

/** Bulleted list helper. */
function bullets(s, items, o) {
  s.addText(
    items.map((t, i) => ({
      text: t, options: { bullet: true, breakLine: i < items.length - 1 },
    })),
    {
      isTextBox: true, fontFace: F_BODY, fontSize: o.fontSize || 13,
      color: o.color || SLATE, paraSpaceAfter: o.gap === undefined ? 7 : o.gap,
      lineSpacingMultiple: 1.0, margin: 0,
      x: o.x, y: o.y, w: o.w, h: o.h,
    }
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 1 — Title
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: INK };

  // Faint knob-grid motif in the corner (config knobs)
  for (let r = 0; r < 4; r++) {
    for (let c = 0; c < 7; c++) {
      s.addShape(pres.ShapeType.roundRect, {
        x: 9.55 + c * 0.5, y: 4.55 + r * 0.5, w: 0.28, h: 0.28, rectRadius: 0.2,
        fill: { color: (r + c) % 5 === 0 ? AMBER : "222D3A" },
        line: { color: "222D3A", width: 0 },
      });
    }
  }

  s.addText("SANDISK HACKATHON  ·  TEAM ASTERIX  ·  2026", {
    x: M, y: 1.28, w: CW, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F_BODY, fontSize: 11.5, bold: true, color: AMBER, charSpacing: 2.6,
  });
  s.addText("UVM Configuration\nIntelligence", {
    x: M, y: 1.66, w: 9.6, h: 1.9, isTextBox: true, margin: 0,
    fontFace: F_HEAD, fontSize: 52, bold: true, color: WHITE, lineSpacingMultiple: 0.94,
  });
  s.addText(
    "Turning raw UVM simulation logs into ranked failure causes, deterministic-bug isolation, "
    + "and a recommended configuration that is both fast and safe.",
    {
      x: M, y: 3.66, w: 8.3, h: 0.8, isTextBox: true, margin: 0,
      fontFace: F_BODY, fontSize: 15, color: "AEB9C4", lineSpacingMultiple: 1.15,
    });

  const stats = [
    ["50,000", "runs in the corpus"],
    ["1.01 M", "log lines parsed"],
    ["2.0 s", "full-corpus parse"],
    ["0.88", "risk-model ROC-AUC"],
  ];
  stats.forEach(([v, l], i) => {
    const x = M + i * 2.28;
    s.addText(v, {
      x, y: 4.78, w: 2.1, h: 0.55, isTextBox: true, margin: 0,
      fontFace: F_HEAD, fontSize: 30, bold: true, color: AMBER,
    });
    s.addText(l, {
      x, y: 5.34, w: 2.1, h: 0.3, isTextBox: true, margin: 0,
      fontFace: F_BODY, fontSize: 11, color: "8B98A5",
    });
  });

  s.addText("Presented by  ______________________        Reviewer  ______________________", {
    x: M, y: 6.55, w: CW, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F_BODY, fontSize: 11, color: "5A6875",
  });
  pageNo += 1;
  s.addNotes(
    "Opening line: verification teams drown in log volume but still triage failures by hand. "
    + "This project reads the logs, finds which configuration combinations cause failures, "
    + "separates real RTL bugs from seed noise, and recommends a safe configuration. "
    + "Everything you will see runs end to end on a 50,000-run corpus."
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 2 — Problem & Objectives
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = lightSlide("The problem", "Regression logs answer 'what', never 'why'");

  card(s, M, 1.72, 5.55, 4.62);
  s.addText("Where verification time goes today", {
    x: M + 0.34, y: 1.98, w: 4.9, h: 0.32, isTextBox: true, margin: 0,
    fontFace: F_HEAD, fontSize: 16.5, bold: true, color: INK,
  });
  bullets(s, [
    "A single nightly regression emits over a million log lines; triage is manual and does not scale.",
    "A failing run reports that it failed — not which combination of knobs made it fail.",
    "Seed-noise flakes and genuine deterministic RTL bugs look identical in a log file.",
    "Config tuning is folklore: nobody can state the fastest setting that still meets a risk budget.",
    "Ad-hoc scripts are written per debug session and thrown away — nothing accumulates.",
  ], { x: M + 0.34, y: 2.44, w: 4.9, h: 3.7, fontSize: 12.5, gap: 11 });

  const objs = [
    ["01", "Ingest at scale", "Parse arbitrary UVM log dumps into structured run and error tables in seconds."],
    ["02", "Rank the causes", "Attribute failure risk to the configuration knobs an engineer can actually set."],
    ["03", "Isolate real bugs", "Separate deterministic RTL failures from seed-dependent noise, automatically."],
    ["04", "Recommend a config", "Maximise throughput subject to an explicit predicted-risk ceiling."],
  ];
  const bx = M + 5.85, bw = (CW - 5.85 - 0.3) / 2, bh = 2.22;
  objs.forEach(([n, t, d], i) => {
    const x = bx + (i % 2) * (bw + 0.3);
    const y = 1.72 + Math.floor(i / 2) * (bh + 0.18);
    card(s, x, y, bw, bh, { fill: WHITE });
    chip(s, x + 0.28, y + 0.28, n, AMBER, INK);
    s.addText(t, {
      x: x + 0.75, y: y + 0.30, w: bw - 1.0, h: 0.32, isTextBox: true, margin: 0,
      fontFace: F_HEAD, fontSize: 15, bold: true, color: INK,
    });
    s.addText(d, {
      x: x + 0.28, y: y + 0.82, w: bw - 0.56, h: 1.2, isTextBox: true, margin: 0,
      fontFace: F_BODY, fontSize: 12, color: SLATE, lineSpacingMultiple: 1.08,
    });
  });

  s.addNotes(
    "Frame the pain first, then the four objectives. Each objective maps to a component you will "
    + "see later: parser, risk model, fingerprinting, recommender."
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 3 — Solution overview
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = lightSlide("Solution overview", "Six stages, one upload, one report",
    "Drop .log files on the dashboard — the whole chain runs on a worker thread and streams progress back to the UI.");

  const items = [
    ["01", "Log ingestion", "Single-pass parser with startswith guards ahead of any regex. 1,015,872 lines in 2.0 s, zero malformed blocks.", AMBER],
    ["02", "Failure-risk model", "LightGBM on configuration knobs only, explained with SHAP TreeExplainer. Global ranking plus per-value attribution.", AMBER],
    ["03", "Failure fingerprinting", "Error text masked to seed-invariant templates, TF-IDF + DBSCAN clustering, determinism score per cluster.", AMBER],
    ["04", "Trade-off frontier", "Pareto frontier over throughput versus predicted risk, grouped on the top SHAP-ranked discrete settings.", TEAL],
    ["05", "Recommender", "Optuna TPE over two surrogates — risk classifier and pass-only throughput regressor — under a 2 % risk ceiling.", TEAL],
    ["06", "Config diff", "Aggregate pass/fail distribution shift plus nearest-twin diffing that names the exact settings that flipped.", TEAL],
  ];
  const cw2 = (CW - 0.6) / 3, ch2 = 2.02;
  items.forEach(([n, t, d, col], i) => {
    const x = M + (i % 3) * (cw2 + 0.3);
    const y = 2.06 + Math.floor(i / 3) * (ch2 + 0.26);
    card(s, x, y, cw2, ch2);
    chip(s, x + 0.28, y + 0.26, n, col, INK);
    s.addText(t, {
      x: x + 0.76, y: y + 0.28, w: cw2 - 1.0, h: 0.32, isTextBox: true, margin: 0,
      fontFace: F_HEAD, fontSize: 15, bold: true, color: INK,
    });
    s.addText(d, {
      x: x + 0.28, y: y + 0.80, w: cw2 - 0.56, h: 1.1, isTextBox: true, margin: 0,
      fontFace: F_BODY, fontSize: 11.5, color: SLATE, lineSpacingMultiple: 1.06,
    });
  });

  s.addText(
    "Every stage is wrapped independently — if one fails, the rest of the report still renders and the failure is recorded in the stage log rather than killing the job.",
    { x: M, y: 6.42, w: CW, h: 0.34, isTextBox: true, margin: 0,
      fontFace: F_BODY, fontSize: 12, italic: true, color: AMBER_D });

  s.addNotes("Stress the fault isolation line at the bottom — it is a real engineering decision, not a slogan.");
}

// ═══════════════════════════════════════════════════════════════════════════
// 4 — Architecture
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = darkSlide("System architecture", "Upload → parse → fan-out → one JSON payload");

  const box = (x, y, w, h, title, sub, accent) => {
    s.addShape(pres.ShapeType.roundRect, {
      x, y, w, h, rectRadius: 0.07,
      fill: { color: PANEL }, line: { color: accent || "2E3B4A", width: 1 },
    });
    s.addText(title, {
      x: x + 0.14, y: y + 0.13, w: w - 0.28, h: 0.28, isTextBox: true, margin: 0,
      fontFace: F_BODY, fontSize: 12.5, bold: true, color: accent || WHITE, align: "center",
    });
    if (sub) s.addText(sub, {
      x: x + 0.10, y: y + 0.42, w: w - 0.20, h: h - 0.5, isTextBox: true, margin: 0,
      fontFace: F_BODY, fontSize: 9.5, color: "93A0AD", align: "center", lineSpacingMultiple: 1.04,
    });
  };
  const arrow = (x1, y1, x2, y2) => {
    s.addShape(pres.ShapeType.line, {
      x: x1, y: y1, w: x2 - x1, h: y2 - y1,
      line: { color: "4A5A6B", width: 1.5, endArrowType: "triangle" },
    });
  };

  // Row 1 — client / service / worker
  box(M, 1.78, 3.5, 0.86, "React 18 + Vite UI", "dropzone · polling · 7 tabs", AMBER);
  box(M + 4.3, 1.78, 3.5, 0.86, "FastAPI service", "/analyze · /jobs · /runs · /diff", AMBER);
  box(M + 8.6, 1.78, 3.47, 0.86, "Worker thread", "job registry · progress callback", AMBER);
  arrow(M + 3.55, 2.21, M + 4.25, 2.21);
  arrow(M + 7.85, 2.21, M + 8.55, 2.21);

  // Row 2 — parser
  box(M, 3.02, CW, 0.78, "uvm_intel.log_parser  —  single pass, shared grammar with the generator",
    "runs frame (config + metrics + verdict)   ·   errors frame (severity, component, tag, masked template)", TEAL);
  arrow(M + 6.0, 2.68, M + 6.0, 2.98);

  // Row 3 — analytics fan-out
  const stages = [
    ["risk_model", "LightGBM + SHAP"],
    ["fingerprints", "TF-IDF + DBSCAN"],
    ["pareto", "frontier search"],
    ["config_diff", "nearest twin"],
    ["recommender", "Optuna TPE"],
  ];
  const sw = (CW - 4 * 0.24) / 5;
  stages.forEach(([t, d], i) => {
    const x = M + i * (sw + 0.24);
    box(x, 4.32, sw, 0.94, t, d);
    arrow(x + sw / 2, 3.84, x + sw / 2, 4.28);
  });

  // Row 4 — payload
  box(M + 1.6, 5.62, CW - 3.2, 0.78, "One JSON-serialisable payload  →  dashboard + /export",
    "per-stage timing log · parse stats · every stage independently fault-isolated", AMBER);
  stages.forEach((_, i) => {
    const x = M + i * (sw + 0.24) + sw / 2;
    arrow(x, 5.30, Math.min(Math.max(x, M + 2.2), M + CW - 2.2), 5.58);
  });

  s.addNotes(
    "Walk left to right, top to bottom. Key points: the log grammar lives in one module shared by "
    + "generator and parser so they cannot drift; analysis runs off the request thread so the UI stays "
    + "responsive; the five analytics stages are independent, so a failure in one still yields a report."
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 5 — Dataset & generation
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = lightSlide("Dataset", "A synthetic corpus we can grade ourselves",
    "Real regression logs come with no answer key. We generated ours, so every discovery can be scored against known truth.");

  card(s, M, 1.86, 7.15, 4.5);
  s.addText("How the corpus is generated", {
    x: M + 0.32, y: 2.10, w: 6.5, h: 0.32, isTextBox: true, margin: 0,
    fontFace: F_HEAD, fontSize: 16.5, bold: true, color: INK,
  });
  bullets(s, [
    "Grammar first: log_format.py is the single source of truth for the log syntax — the generator writes it and the parser reads it, so the two cannot drift apart.",
    "Vectorised sampling: all 50,000 runs are drawn with NumPy over a weighted configuration space; only the final text rendering loops.",
    "Deliberately lopsided weights so the model faces a realistic, imbalanced design space rather than a uniform grid.",
    "Failure probability is composed rule-by-rule, then the verdict, error trace, UVM report summary and metrics are rendered to match.",
    "Base failure probability is fixed at 1.2 % so a clean configuration sits below the 2 % ceiling the recommender optimises against.",
  ], { x: M + 0.32, y: 2.56, w: 6.5, h: 3.0, fontSize: 12, gap: 9 });

  s.addText("python -m uvm_intel.generate_logs --n-runs 50000 --parts 10", {
    x: M + 0.32, y: 5.78, w: 6.5, h: 0.34, isTextBox: true, margin: 0.04,
    fontFace: F_MONO, fontSize: 11, color: INK, fill: { color: "EAEEF3" },
  });

  // Right column — donut + schema chips
  const rx = M + 7.45, rw = CW - 7.45;
  card(s, rx, 1.86, rw, 2.62, { fill: WHITE });
  s.addText("Verdict split across 50,000 runs", {
    x: rx + 0.26, y: 2.02, w: rw - 0.52, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F_HEAD, fontSize: 13.5, bold: true, color: INK,
  });
  s.addChart(pres.ChartType.doughnut,
    [{ name: "Verdict", labels: ["Pass", "Fail"], values: [75.96, 24.04] }],
    {
      x: rx + 0.1, y: 2.32, w: rw - 0.2, h: 2.02,
      holeSize: 58, chartColors: [TEAL, CRIMSON],
      showLegend: true, legendPos: "b", legendFontSize: 10, legendColor: SLATE,
      showValue: true, dataLabelColor: WHITE, dataLabelFontSize: 11,
      dataLabelFormatCode: '0.0"%"', showTitle: false,
    });

  const facts = [
    ["11", "configuration knobs"],
    ["2", "environment readings"],
    ["8", "UVM test sequences"],
    ["7", "error-tag taxonomy"],
    ["4", "outcome metrics"],
    ["~56 MB", "corpus, 10 files"],
  ];
  const fw = (rw - 0.24) / 2, fh = 0.54;
  facts.forEach(([v, l], i) => {
    const x = rx + (i % 2) * (fw + 0.24);
    const y = 4.62 + Math.floor(i / 2) * (fh + 0.2);
    s.addText(v, {
      x, y, w: fw, h: 0.3, isTextBox: true, margin: 0,
      fontFace: F_HEAD, fontSize: 19, bold: true, color: AMBER_D,
    });
    s.addText(l, {
      x, y: y + 0.3, w: fw, h: 0.24, isTextBox: true, margin: 0,
      fontFace: F_BODY, fontSize: 10, color: MUTED,
    });
  });

  s.addNotes(
    "Config knobs: test_name, cache_policy, test_mode_enabled, queue_depth, num_channels, num_planes, "
    + "ecc_mode, scrambler_enable, burst_length, clock_freq_mhz, prefetch_depth. Environment: voltage_mv "
    + "and temperature_c, both normally distributed. Outcomes: execution_time_ms, throughput_mbps, cycles, "
    + "error tags. Overall failure rate lands at 24.04 %."
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 6 — Ground truth rules
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = lightSlide("Ground truth", "Seven failure rules, planted on purpose",
    "Written to data/uvm_ground_truth.json at generation time — the pipeline is graded on whether it rediscovers them.");

  const rows = [
    [["Rule", "Condition", "Effect on failure", "Runs", "Fail rate", "Lift"], true],
    [["R1", "test_name = Back_To_Back_Program + cache_policy = Adaptive", "set 0.85, FIFO_OVERFLOW", "2,891", "0.851", "4.19×"]],
    [["R2", "test_mode_enabled = 1", "+0.35", "13,999", "0.473", "3.16×"]],
    [["R3", "queue_depth ≥ 32 + ecc_mode = Disabled", "+0.35, ECC_UNCORRECTABLE", "1,976", "0.574", "2.53×"]],
    [["R4", "temperature_c > 85 + voltage_mv < 1100", "+0.30, RETENTION_FAIL", "281", "0.559", "2.34×"]],
    [["R5", "num_planes = 4 + burst_length = 64 + scrambler_enable = 1", "set 0.98, deterministic", "815", "0.987", "4.33×"]],
    [["R6", "clock_freq_mhz ≥ 1000 + prefetch_depth > 8", "+0.30, TIMEOUT", "8,014", "0.475", "2.43×"]],
    [["R7", "cache_policy = Disabled + queue_depth ≥ 16", "+0.30, DATA_MISMATCH", "2,800", "0.493", "2.19×"]],
  ];
  const tblRows = rows.map(([cells, head]) =>
    cells.map((t, i) => ({
      text: t,
      options: {
        bold: !!head || i === 0,
        color: head ? WHITE : (i === 0 ? AMBER_D : SLATE),
        fill: { color: head ? INK : (i % 2 ? WHITE : "FAFBFC") },
        fontSize: head ? 11 : 10.5,
        align: i >= 3 ? "right" : "left",
        valign: "middle",
        fontFace: F_BODY,
      },
    }))
  );
  s.addTable(tblRows, {
    x: M, y: 1.90, w: 8.55, colW: [0.6, 3.55, 2.25, 0.75, 0.75, 0.65],
    rowH: 0.4, border: { type: "solid", color: LINE, pt: 1 },
    margin: 0.06,
  });

  const nx = M + 8.85, nw = CW - 8.85;
  card(s, nx, 1.90, nw, 1.95, { fill: WHITE });
  chip(s, nx + 0.26, 2.12, "R5", CRIMSON, WHITE, 0.46);
  s.addText("The planted RTL bug", {
    x: nx + 0.84, y: 2.16, w: nw - 1.1, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F_HEAD, fontSize: 14.5, bold: true, color: INK,
  });
  s.addText(
    "R5 emits a byte-identical error trace on every hit, whatever the seed. It is the target the "
    + "fingerprinting stage has to isolate from ordinary flakes.",
    { x: nx + 0.26, y: 2.68, w: nw - 0.52, h: 1.0, isTextBox: true, margin: 0,
      fontFace: F_BODY, fontSize: 11.5, color: SLATE, lineSpacingMultiple: 1.08 });

  card(s, nx, 3.99, nw, 2.32, { fill: WHITE });
  chip(s, nx + 0.26, 4.21, "✓", TEAL, WHITE, 0.46);
  s.addText("Graded, not guessed", {
    x: nx + 0.84, y: 4.25, w: nw - 1.1, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F_HEAD, fontSize: 14.5, bold: true, color: INK,
  });
  bullets(s, [
    "R1 and R2 are the two rules named in the problem brief.",
    "Every lift figure shown is measured on the corpus, not assumed.",
    "Any future model change is re-scored against the same answer key.",
  ], { x: nx + 0.26, y: 4.76, w: nw - 0.52, h: 1.4, fontSize: 11.5, gap: 8 });

  s.addNotes(
    "Lift = failure rate when the rule fires ÷ failure rate when it does not. R4 is deliberately "
    + "rare (281 runs) to test whether the pipeline can still find a low-support but high-lift rule."
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 7 — Risk model
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = lightSlide("Model", "Failure-risk classifier with SHAP attribution",
    "LightGBM gradient boosting on configuration knobs only — the settings an engineer can actually change.");

  card(s, M, 1.92, 6.35, 4.42);
  s.addText("Design decisions that matter", {
    x: M + 0.32, y: 2.16, w: 5.7, h: 0.32, isTextBox: true, margin: 0,
    fontFace: F_HEAD, fontSize: 16.5, bold: true, color: INK,
  });
  bullets(s, [
    "Leakage guard: every outcome column — execution_time_ms, throughput_mbps, cycles, UVM error counts, verdict, error tags, traces — is excluded from the feature set by construction.",
    "seed and run_id are dropped too: a seed is not a setting anyone can ship.",
    "Categorical knobs are cast to pandas category and handled natively by LightGBM — no one-hot blow-up.",
    "SHAP TreeExplainer gives global importance and per-value attribution, so the output is 'cache_policy = Adaptive raises risk', not just 'cache_policy matters'.",
    "Held-out split reports ROC-AUC, average precision, accuracy, F1, ROC curve and confusion matrix — all surfaced in the dashboard.",
  ], { x: M + 0.32, y: 2.62, w: 5.7, h: 3.5, fontSize: 12, gap: 9 });

  const rx = M + 6.65, rw = CW - 6.65;
  card(s, rx, 1.92, rw, 1.26, { fill: INK, line: INK });
  s.addText("0.88", {
    x: rx + 0.3, y: 2.06, w: 2.0, h: 0.72, isTextBox: true, margin: 0,
    fontFace: F_HEAD, fontSize: 40, bold: true, color: AMBER,
  });
  s.addText("Typical held-out ROC-AUC\non the bundled 50k corpus", {
    x: rx + 2.35, y: 2.16, w: rw - 2.65, h: 0.7, isTextBox: true, margin: 0,
    fontFace: F_BODY, fontSize: 12, color: "AEB9C4", lineSpacingMultiple: 1.1,
  });

  card(s, rx, 3.32, rw, 3.02, { fill: WHITE });
  s.addText("Signal strength the model has to learn", {
    x: rx + 0.28, y: 3.50, w: rw - 0.56, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F_HEAD, fontSize: 14, bold: true, color: INK,
  });
  s.addText("Observed failure-rate lift per embedded rule", {
    x: rx + 0.28, y: 3.78, w: rw - 0.56, h: 0.26, isTextBox: true, margin: 0,
    fontFace: F_BODY, fontSize: 10.5, color: MUTED,
  });
  s.addChart(pres.ChartType.bar,
    [{ name: "Lift", labels: ["R7", "R4", "R6", "R3", "R2", "R1", "R5"],
       values: [2.19, 2.34, 2.43, 2.53, 3.16, 4.19, 4.33] }],
    {
      x: rx + 0.05, y: 4.02, w: rw - 0.15, h: 2.22,
      barDir: "bar", barGapWidthPct: 45, chartColors: [AMBER],
      showLegend: false, showTitle: false,
      showValue: true, dataLabelPosition: "outEnd", dataLabelColor: SLATE,
      dataLabelFontSize: 10, dataLabelFormatCode: '0.00"×"',
      catAxisLabelColor: SLATE, catAxisLabelFontSize: 10,
      valAxisLabelColor: MUTED, valAxisLabelFontSize: 9, valAxisMaxVal: 5,
      valGridLine: { color: "EDF1F5", size: 1 }, catGridLine: { style: "none" },
    });

  s.addNotes(
    "The leakage guard is the point to dwell on: it is trivial to score 0.99 by feeding the model "
    + "uvm_error_count, and completely useless — the model would be reading the answer. Restricting "
    + "features to settable knobs is what makes the SHAP ranking actionable."
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 8 — Fingerprints / Pareto / Recommender / Diff
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = lightSlide("Analytics engine", "Four techniques behind the four analysis tabs");

  const quads = [
    {
      n: "A", t: "Failure fingerprinting", col: CRIMSON,
      lines: [
        "Every error message is masked to a seed-invariant template — 0x0004a2c0 → <ADDR>, 32 → <N>.",
        "TF-IDF is fitted over distinct templates, not runs: a 50k corpus collapses to ~7 templates, so DBSCAN stays trivial.",
        "determinism = 1 − (distinct raw traces ÷ runs in cluster).",
      ],
      foot: "c1  n=804  PROTOCOL_VIOLATION  det=0.999  →  deterministic RTL bug\nc2  n=3040  TIMEOUT  det=0.000  →  seed-dependent noise",
    },
    {
      n: "B", t: "Trade-off frontier", col: TEAL,
      lines: [
        "Pareto frontier over throughput versus predicted risk.",
        "Points are grouped on the top-4 SHAP-ranked discrete settings — continuous readings would make every run its own configuration.",
        "Yields 318 configurations of 3–109 runs each.",
      ],
      foot: "Predicted risk tracks observed failure rate: 0.139 vs 0.139.",
    },
    {
      n: "C", t: "Recommender", col: TEAL,
      lines: [
        "Optuna TPE search over two surrogates: the risk classifier and a throughput regressor fitted on passing runs only.",
        "Objective is 'throughput when it works', not throughput averaged with degraded failures.",
        "Maximise throughput subject to predicted risk ≤ 2 %, applied as a penalty so TPE learns the constraint shape.",
      ],
      foot: "If the ceiling is unreachable the API says so and returns the lowest-risk configs found.",
    },
    {
      n: "D", t: "Config diff", col: AMBER,
      lines: [
        "Aggregate delta: how each setting's distribution shifts between passing and failing runs.",
        "Nearest-twin: each failing run is paired with its most similar passing run, recording exactly which settings differ.",
        "Both views are scoped to identical test sequences.",
      ],
      foot: "Numeric fields only count as changed at ≥ 0.5 SD — otherwise voltage and temperature bury the settings that matter.",
    },
  ];

  const qw = (CW - 0.3) / 2, qh = 2.32;
  quads.forEach((q, i) => {
    const x = M + (i % 2) * (qw + 0.3);
    const y = 1.72 + Math.floor(i / 2) * (qh + 0.24);
    card(s, x, y, qw, qh);
    chip(s, x + 0.28, y + 0.26, q.n, q.col, WHITE);
    s.addText(q.t, {
      x: x + 0.76, y: y + 0.27, w: qw - 1.0, h: 0.32, isTextBox: true, margin: 0,
      fontFace: F_HEAD, fontSize: 15.5, bold: true, color: INK,
    });
    bullets(s, q.lines, { x: x + 0.30, y: y + 0.74, w: qw - 0.6, h: 1.1, fontSize: 11, gap: 5 });
    s.addText(q.foot, {
      x: x + 0.30, y: y + qh - 0.66, w: qw - 0.6, h: 0.56, isTextBox: true, margin: 0,
      fontFace: F_MONO, fontSize: 9, color: AMBER_D, lineSpacingMultiple: 1.05,
    });
  });

  s.addNotes(
    "The determinism score is the headline result: 804 runs, 804 different seeds, one distinct raw "
    + "trace. That is exactly the separation between a real RTL bug and seed noise that the brief asks for. "
    + "min_samples=1 in DBSCAN is intentional — a template seen once is a rare bug, not noise to discard."
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 9 — Dashboard I: Executive Summary
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = lightSlide("Dashboard · tab 1 of 7", "Executive Summary",
    "The one screen a lead opens first: how bad is this regression, and what is driving it?");

  placeholder(s, M, 1.92, 8.1, 4.44, "Executive Summary tab — full view",
    "Capture the whole tab at 1440 px wide after running the bundled sample");

  const rx = M + 8.4, rw = CW - 8.4;
  card(s, rx, 1.92, rw, 4.44, { fill: WHITE });
  s.addText("What is on this screen", {
    x: rx + 0.28, y: 2.12, w: rw - 0.56, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F_HEAD, fontSize: 15.5, bold: true, color: INK,
  });
  bullets(s, [
    "KPI strip — runs parsed, pass/fail counts, failure rate, error lines.",
    "Pass/fail donut and a risk-band histogram of predicted failure probability.",
    "Global SHAP importance chart — the ranked cause list.",
    "Failure-mode distribution across the seven error tags.",
    "ROC curve, held-out metrics and confusion matrix for the risk model.",
    "Mean execution time broken down by failure mode.",
  ], { x: rx + 0.28, y: 2.56, w: rw - 0.56, h: 3.6, fontSize: 11.5, gap: 10 });

  s.addNotes(
    "Demo tip: open with the bundled sample so the page is already populated. Point at the SHAP chart "
    + "and name the top knob, then move to the failure-mode distribution."
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 10 — Dashboard II: Fingerprints + Tradeoff
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = lightSlide("Dashboard · tabs 2–3 of 7", "Failure Fingerprints  ·  Trade-off Matrix");

  const pw = (CW - 0.4) / 2;
  placeholder(s, M, 1.86, pw, 3.16, "Failure Fingerprints tab",
    "Show the cluster map with a high-determinism cluster selected");
  placeholder(s, M + pw + 0.4, 1.86, pw, 3.16, "Trade-off Matrix tab",
    "Show the Pareto scatter with the knee point highlighted");

  const blocks = [
    { x: M, t: "Failure Fingerprints", col: CRIMSON, lines: [
      "SVD cluster map — each point a failure cluster, sized by run count.",
      "Cluster table with determinism score, run count, distinct seeds and distinct raw traces.",
      "Drill-down showing the masked template beside a raw trace.",
      "One-click hand-off into the diff viewer for any clustered run.",
    ]},
    { x: M + pw + 0.4, t: "Trade-off Matrix", col: TEAL, lines: [
      "Interactive throughput-versus-risk scatter with the frontier drawn through it.",
      "Three named operating points: peak throughput, knee, and best-safe.",
      "Full frontier table with observed and predicted failure rate per configuration.",
      "Hover any point to read the exact configuration behind it.",
    ]},
  ];
  blocks.forEach((b) => {
    card(s, b.x, 5.16, pw, 1.5, { fill: WHITE });
    chip(s, b.x + 0.26, 5.34, "★", b.col, WHITE, 0.34);
    s.addText(b.t, {
      x: b.x + 0.70, y: 5.34, w: pw - 0.96, h: 0.3, isTextBox: true, margin: 0,
      fontFace: F_HEAD, fontSize: 14, bold: true, color: INK,
    });
    bullets(s, b.lines, { x: b.x + 0.28, y: 5.72, w: pw - 0.56, h: 0.86, fontSize: 10.5, gap: 2 });
  });

  s.addNotes(
    "Fingerprints is the tab to spend the most demo time on — sort the cluster table by determinism "
    + "and show the near-1.0 cluster, then open the drill-down to prove the traces are identical."
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 11 — Dashboard III: Recommendations / Diff / Explorer / Details
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = lightSlide("Dashboard · tabs 4–7 of 7", "Recommendations  ·  Config Diff  ·  Run Explorer  ·  All Details");

  const pw = (CW - 0.6) / 3;
  const cards3 = [
    { t: "Recommendations", hint: "Show the top recommended config and the Optuna history plot", col: TEAL, lines: [
      "Ranked configurations from the TPE search with predicted throughput and risk.",
      "Optimisation history across trials.",
      "The derived search space actually explored.",
    ]},
    { t: "Config Diff", hint: "Show the two-run log diff with divergent settings highlighted", col: AMBER, lines: [
      "Twin-divergence ranking — which settings flip a run from pass to fail.",
      "Interactive two-run log diff viewer.",
      "Closest failing/passing pairs and aggregate deltas per sequence.",
    ]},
    { t: "Run Explorer + All Details", hint: "Show the paged run table, then the parse-stats panel", col: AMBER, lines: [
      "Paged, filterable, sortable table of every parsed run.",
      "Parse stats, per-stage timing log, failure rate by field with lift.",
      "Metric distributions, highest-risk runs, job metadata, column inventory.",
    ]},
  ];
  cards3.forEach((c, i) => {
    const x = M + i * (pw + 0.3);
    placeholder(s, x, 1.80, pw, 2.52, c.t + " tab", c.hint);
    card(s, x, 4.48, pw, 2.06, { fill: WHITE });
    chip(s, x + 0.24, 4.66, "▸", c.col, WHITE, 0.32);
    s.addText(c.t, {
      x: x + 0.66, y: 4.66, w: pw - 0.9, h: 0.3, isTextBox: true, margin: 0,
      fontFace: F_HEAD, fontSize: 13.5, bold: true, color: INK,
    });
    bullets(s, c.lines, { x: x + 0.26, y: 5.04, w: pw - 0.52, h: 1.4, fontSize: 10.5, gap: 5 });
  });

  s.addText(
    "Every tab reads from the same job payload, and the whole report can be downloaded as JSON from /api/jobs/{id}/export.",
    { x: M, y: 6.62, w: CW, h: 0.3, isTextBox: true, margin: 0,
      fontFace: F_BODY, fontSize: 11.5, italic: true, color: AMBER_D });

  s.addNotes("Keep this section brisk in the demo — one sentence per tab, then return to Fingerprints for questions.");
}

// ═══════════════════════════════════════════════════════════════════════════
// 12 — Software stack, API, performance
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = darkSlide("Engineering", "Software stack, API surface and measured performance");

  const stack = [
    ["Frontend", "React 18 · Vite 5 · Recharts · Axios\nCustom dropzone, polling job client, 7 tab views"],
    ["Backend", "FastAPI 0.104 · Uvicorn · python-multipart\nThreaded job registry, CORS, 512 MB upload cap"],
    ["ML & analytics", "LightGBM · SHAP · scikit-learn · Optuna (TPE)\nTF-IDF + DBSCAN · NumPy · pandas"],
    ["Tooling", "Python 3.11 · pytest parser suite · CLI entry points\nShared log grammar module, ground-truth grader"],
  ];
  const sw = (CW - 0.36) / 2, sh = 1.16;
  stack.forEach(([t, d], i) => {
    const x = M + (i % 2) * (sw + 0.36);
    const y = 1.80 + Math.floor(i / 2) * (sh + 0.22);
    s.addShape(pres.ShapeType.roundRect, {
      x, y, w: sw, h: sh, rectRadius: 0.06,
      fill: { color: PANEL }, line: { color: "2E3B4A", width: 1 },
    });
    s.addText(t, {
      x: x + 0.26, y: y + 0.16, w: sw - 0.5, h: 0.3, isTextBox: true, margin: 0,
      fontFace: F_HEAD, fontSize: 14.5, bold: true, color: AMBER,
    });
    s.addText(d, {
      x: x + 0.26, y: y + 0.50, w: sw - 0.5, h: 0.6, isTextBox: true, margin: 0,
      fontFace: F_BODY, fontSize: 11.5, color: "AEB9C4", lineSpacingMultiple: 1.08,
    });
  });

  // API list
  s.addText("REST API", {
    x: M, y: 4.44, w: sw, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F_HEAD, fontSize: 15, bold: true, color: WHITE,
  });
  s.addText(
    "GET    /api/health              liveness + bundled-sample availability\n"
    + "POST   /api/analyze             upload .log files, start a job\n"
    + "POST   /api/analyze-sample      analyse the bundled corpus\n"
    + "GET    /api/jobs/{id}           status + progress\n"
    + "GET    /api/jobs/{id}/result    full analysis payload\n"
    + "GET    /api/jobs/{id}/runs      paged run table\n"
    + "GET    /api/jobs/{id}/diff      field-by-field diff of two runs\n"
    + "GET    /api/jobs/{id}/export    download payload as JSON",
    { x: M, y: 4.78, w: sw, h: 1.9, isTextBox: true, margin: 0,
      fontFace: F_MONO, fontSize: 9.5, color: "9AA7B4", lineSpacingMultiple: 1.14 });

  // Performance
  const px = M + sw + 0.36;
  s.addText("Measured performance", {
    x: px, y: 4.44, w: sw, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F_HEAD, fontSize: 15, bold: true, color: WHITE,
  });
  const perf = [
    [["Corpus", "Parse", "Full analysis"], true],
    [["5,000 runs", "~0.6 s", "9.6 s"]],
    [["10,000 runs", "~1.2 s", "27 s"]],
    [["50,000 runs", "2.0 s", "—"]],
  ];
  s.addTable(
    perf.map(([cells, head]) => cells.map((t, i) => ({
      text: t,
      options: {
        bold: !!head, color: head ? INK : "C8D2DC",
        fill: { color: head ? AMBER : PANEL },
        fontSize: 10.5, fontFace: F_BODY, valign: "middle",
        align: i === 0 ? "left" : "right",
      },
    }))),
    { x: px, y: 4.78, w: sw, colW: [sw * 0.42, sw * 0.27, sw * 0.31], rowH: 0.34,
      border: { type: "solid", color: "2E3B4A", pt: 1 }, margin: 0.07 }
  );
  s.addText(
    "Python 3.11, 8 cores.  1,015,872 lines parsed with zero malformed blocks and zero unparsed lines.  "
    + "Job-level tunables: max_risk, n_trials, dbscan_eps, enable_recommender.",
    { x: px, y: 6.20, w: sw, h: 0.52, isTextBox: true, margin: 0,
      fontFace: F_BODY, fontSize: 10.5, color: "7E8C99", lineSpacingMultiple: 1.08 });

  s.addNotes(
    "If asked why a worker thread rather than a process pool: the heavy stages release the GIL "
    + "(NumPy, LightGBM), and a thread keeps the job registry and progress callback in one address space."
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 13 — Future scope
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = lightSlide("Roadmap", "Future scope",
    "Ordered by the value each item adds against the effort it needs.");

  const near = [
    ["RAG copilot", "ChromaDB + LangChain natural-language Q&A over the parsed corpus — scoped in the plan, deferred because it needs an LLM endpoint and key."],
    ["Regression-over-time", "Persist jobs to a database and trend failure rate, SHAP ranking and cluster membership across nightly runs."],
    ["CI integration", "A gate that fails the build when a new deterministic cluster appears or predicted risk crosses the ceiling."],
  ];
  const later = [
    ["Real log adapters", "Pluggable grammars for VCS, Questa and Xcelium output so the pipeline runs on production regressions, not just the synthetic corpus."],
    ["Coverage-aware recommendation", "Add functional-coverage closure as a third objective beside throughput and risk."],
    ["Automatic triage routing", "Map each fingerprint cluster to an owning component and open the ticket with the twin-diff attached."],
    ["Live streaming ingest", "Consume logs as the regression runs, so risky configurations are flagged mid-flight instead of at the end."],
  ];

  const colW = (CW - 0.4) / 2;
  const heads = [["Next", "Near term", AMBER, near], ["Then", "Longer term", TEAL, later]];
  heads.forEach(([, title, col, items], ci) => {
    const x = M + ci * (colW + 0.4);
    s.addText(title, {
      x, y: 1.86, w: colW, h: 0.32, isTextBox: true, margin: 0,
      fontFace: F_HEAD, fontSize: 17, bold: true, color: INK,
    });
    items.forEach(([t, d], i) => {
      const y = 2.30 + i * 1.09;
      card(s, x, y, colW, 0.95, { fill: WHITE });
      chip(s, x + 0.24, y + 0.20, String(i + 1), col, ci === 0 ? INK : WHITE, 0.32);
      s.addText(t, {
        x: x + 0.66, y: y + 0.14, w: colW - 0.9, h: 0.26, isTextBox: true, margin: 0,
        fontFace: F_HEAD, fontSize: 13, bold: true, color: INK,
      });
      s.addText(d, {
        x: x + 0.66, y: y + 0.40, w: colW - 0.9, h: 0.48, isTextBox: true, margin: 0,
        fontFace: F_BODY, fontSize: 10.5, color: SLATE, lineSpacingMultiple: 1.04,
      });
    });
  });

  s.addNotes(
    "Be straight about the RAG copilot: it was a listed bonus, it is not built, and the reason is a "
    + "product decision about an LLM endpoint rather than a technical blocker. Everything else in the plan is in place."
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 14 — Closing
// ═══════════════════════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: INK };
  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 5; c++) {
      s.addShape(pres.ShapeType.roundRect, {
        x: 10.55 + c * 0.5, y: 5.05 + r * 0.5, w: 0.28, h: 0.28, rectRadius: 0.2,
        fill: { color: (r + c) % 4 === 0 ? AMBER : "222D3A" },
        line: { color: "222D3A", width: 0 },
      });
    }
  }

  s.addText("IN CLOSING", {
    x: M, y: 1.30, w: CW, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F_BODY, fontSize: 11.5, bold: true, color: AMBER, charSpacing: 2.6,
  });
  s.addText("From a million log lines\nto one recommended configuration", {
    x: M, y: 1.66, w: 10.6, h: 1.6, isTextBox: true, margin: 0,
    fontFace: F_HEAD, fontSize: 38, bold: true, color: WHITE, lineSpacingMultiple: 1.0,
  });

  const takeaways = [
    ["Parsed", "1,015,872 lines in 2.0 s, zero malformed blocks — ingestion is not the bottleneck."],
    ["Explained", "Leakage-controlled LightGBM with SHAP names the knobs, not just the symptoms."],
    ["Separated", "A determinism score isolates a real RTL bug from 3,000 seed-dependent flakes."],
    ["Recommended", "Optuna TPE returns the fastest configuration that still meets a 2 % risk ceiling."],
  ];
  const tw = (CW - 0.72) / 4;
  takeaways.forEach(([t, d], i) => {
    const x = M + i * (tw + 0.24);
    s.addText(t, {
      x, y: 3.58, w: tw, h: 0.32, isTextBox: true, margin: 0,
      fontFace: F_HEAD, fontSize: 16, bold: true, color: AMBER,
    });
    s.addText(d, {
      x, y: 3.94, w: tw, h: 1.0, isTextBox: true, margin: 0,
      fontFace: F_BODY, fontSize: 11, color: "9AA7B4", lineSpacingMultiple: 1.1,
    });
  });

  s.addText("Thank you  ·  Questions", {
    x: M, y: 5.62, w: 7.5, h: 0.5, isTextBox: true, margin: 0,
    fontFace: F_HEAD, fontSize: 24, bold: true, color: WHITE,
  });
  s.addText("Team Asterix  ·  SanDisk Hackathon 2026", {
    x: M, y: 6.14, w: 7.5, h: 0.3, isTextBox: true, margin: 0,
    fontFace: F_BODY, fontSize: 11.5, color: "6E7C89",
  });
  pageNo += 1;
  s.addNotes("Close on the determinism result — it is the most distinctive thing the project does.");
}

pres.writeFile({ fileName: "UVM_Configuration_Intelligence.pptx" })
  .then((f) => console.log("wrote " + f));
