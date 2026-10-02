"""Build docs/demo/foae_live_demo.html.

Inlines docs/demo/demo_runs.json (MODE B) so the page opens from file:// with a
double-click, and ALSO attempts fetch() (MODE A) so a served copy picks up a
regenerated demo_runs.json without a rebuild. Run after regenerating the runs:

    python -m foae.pipeline demo -n 24 --seed 42
    python docs/demo/build_demo.py

Both are run from the repository root.
"""
import io
import json
from pathlib import Path

RUNS = Path("docs/demo/demo_runs.json")
OUT = Path("docs/demo/foae_live_demo.html")

data = json.loads(RUNS.read_text(encoding="utf-8"))
# Guard against a literal </script> ever appearing inside the embedded JSON.
blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FOAE — Live Attribution Demo</title>
<style>
:root{
  --bg:#f6f5f2; --panel:#fff; --panel-2:#efedE8; --ink:#1b1a18; --ink-2:#6b6862;
  --rule:#d8d4cc; --fault:#a82f1c; --ok:#1f6b43; --abstain:#8a6d1f;
  --wire-sig:#b9b4aa; --wire-rail:#7d8a99; --accent:#24506e;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --bg:#16181a; --panel:#1e2124; --panel-2:#25292d; --ink:#e8e6e1; --ink-2:#9a968e;
    --rule:#33383d; --fault:#e06a52; --ok:#5fbe8b; --abstain:#d4ac4a;
    --wire-sig:#4a4f55; --wire-rail:#7d8a99; --accent:#6fa8cf;
  }
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
  font-size:14px;line-height:1.45}
.wrap{max-width:1180px;margin:0 auto;padding:18px 16px 40px}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:baseline;
  border-bottom:2px solid var(--ink);padding-bottom:10px;margin-bottom:14px}
h1{font-size:20px;margin:0;letter-spacing:.02em}
.sub{color:var(--ink-2);font-size:12.5px}
.banner{margin:0 0 14px;padding:8px 12px;border:1px solid var(--abstain);
  border-left:4px solid var(--abstain);background:color-mix(in srgb,var(--abstain) 9%,transparent);
  font-size:12.5px;color:var(--ink)}
.banner b{letter-spacing:.04em;text-transform:uppercase;font-size:11.5px}
.bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:16px}
button{font-family:var(--sans);font-size:14px;font-weight:600;cursor:pointer;
  padding:10px 18px;border-radius:6px;border:1px solid var(--ink);
  background:var(--ink);color:var(--bg)}
button:hover{opacity:.88}
button.ghost{background:transparent;color:var(--ink);font-weight:500}
button:disabled{opacity:.45;cursor:default}
.tally{display:flex;gap:14px;margin-left:auto;font-family:var(--mono);font-size:12px;
  color:var(--ink-2);flex-wrap:wrap}
.tally b{color:var(--ink);font-size:14px}
.grid{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:14px}
@media(max-width:900px){.grid{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--rule);border-radius:8px;overflow:hidden}
.card>h2{margin:0;font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--ink-2);padding:9px 12px;border-bottom:1px solid var(--rule);
  background:var(--panel-2);font-weight:600}
.card>.body{padding:12px}
svg{display:block;width:100%;height:auto}
.note{font-size:11.5px;color:var(--ink-2);padding:0 12px 10px;font-family:var(--mono)}
.verdict{padding:14px 12px}
.vhead{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px}
.pill{font-family:var(--mono);font-size:11px;letter-spacing:.06em;padding:3px 8px;
  border-radius:999px;border:1px solid currentColor;text-transform:uppercase}
.seg{font-family:var(--mono);font-size:19px;font-weight:600;word-break:break-all}
.good{color:var(--ok)} .bad{color:var(--fault)} .abst{color:var(--abstain)}
dl.kv{display:grid;grid-template-columns:auto 1fr;gap:5px 12px;margin:10px 0 0;
  font-size:12.5px}
dl.kv dt{color:var(--ink-2)}
dl.kv dd{margin:0;font-family:var(--mono);word-break:break-all}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--rule)}
th{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-2);
  font-weight:600}
td.mono,th.mono{font-family:var(--mono)}
tr.win td{background:color-mix(in srgb,var(--accent) 11%,transparent);font-weight:600}
tr.truth td:first-child::after{content:" ◂ truth";color:var(--ink-2);font-weight:400;
  font-size:10.5px;letter-spacing:.04em}
.barcell{position:relative;min-width:80px}
.barcell i{position:absolute;left:8px;top:50%;transform:translateY(-50%);height:9px;
  background:var(--accent);opacity:.35;border-radius:2px}
.barcell span{position:relative;font-family:var(--mono)}
.pids{display:grid;grid-template-columns:repeat(auto-fill,minmax(215px,1fr));gap:8px}
.pid{border:1px solid var(--rule);border-radius:6px;padding:7px 9px;background:var(--panel)}
.pid.anom{border-color:var(--fault);background:color-mix(in srgb,var(--fault) 7%,transparent)}
.pid .n{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.pid .nm{font-family:var(--mono);font-size:11.5px}
.pid .vv{font-family:var(--mono);font-size:12.5px;font-weight:600}
.pid .fl{font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:var(--fault);
  font-weight:600}
.pid .t1{font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:var(--ink-2)}
.hist{max-height:270px;overflow:auto}
.hist table{font-size:12px}
.err{padding:14px;color:var(--fault);font-family:var(--mono);font-size:12.5px}
@keyframes spin{to{transform:rotate(360deg)}}
.spin{display:inline-block;width:13px;height:13px;border:2px solid currentColor;
  border-right-color:transparent;border-radius:50%;animation:spin .6s linear infinite;
  vertical-align:-2px}
.loading{padding:14px 12px}
.stages{list-style:none;margin:10px 0 0;padding:0;font-family:var(--mono);font-size:12px}
.stages li{padding:3px 0;color:var(--ink-2);opacity:.32;
  transition:opacity .18s ease,color .18s ease}
.stages li::before{content:"\25cb  "}
.stages li.on{opacity:1;color:var(--ink)}
.stages li.on::before{content:"\25d0  "}
.stages li.done{opacity:.7;color:var(--ok)}
.stages li.done::before{content:"\25cf  "}
#sch{transition:opacity .2s ease}
button#go[disabled]{opacity:.55}
@media(prefers-reduced-motion:reduce){.spin{animation:none}.stages li{transition:none}}
footer{margin-top:22px;padding-top:10px;border-top:1px solid var(--rule);
  color:var(--ink-2);font-size:11.5px}
footer code{font-family:var(--mono)}
</style>
</head>
<body>
<div class="wrap">

<header>
  <h1>FOAE — Live Attribution Demo</h1>
  <div class="sub">Fault Origin Attribution Engine · Tier-2 footprint attribution over the EPDG</div>
</header>

<p class="banner"><b>Simulation — no hardware validation.</b>
Every verdict below is produced by the real Python engine
(<code>foae/simulator</code> → <code>foae/attribution/footprint.py</code>) and replayed here;
this page renders, it does not attribute. The fault models are written from physical
reasoning with no bench measurement behind them.</p>

<div class="bar">
  <button id="go">⚡ Inject random fault</button>
  <button id="reset" class="ghost">Reset tally</button>
  <div class="tally">
    <span>injected <b id="t-n">0</b></span>
    <span>named <b id="t-named">0</b></span>
    <span>correct <b id="t-ok">0</b></span>
    <span>abstained <b id="t-ab">0</b></span>
    <span>misattributed <b id="t-bad">0</b></span>
  </div>
</div>

<div class="grid">
  <div>
    <div class="card">
      <h2>Harness schematic — sensors → connectors → shared rails → ECU</h2>
      <div class="body" style="padding:6px"><svg id="sch" viewBox="0 0 760 330"
        role="img" aria-label="Harness dependency schematic"></svg></div>
      <div class="note" id="sch-note">press inject to begin</div>
    </div>
    <div class="card" style="margin-top:14px">
      <h2>PID readings this session</h2>
      <div class="body"><div class="pids" id="pids"></div></div>
    </div>
  </div>

  <div>
    <div class="card">
      <h2>Verdict</h2>
      <div id="verdict" class="verdict"><span class="sub">No fault injected yet.</span></div>
    </div>
    <div class="card" style="margin-top:14px">
      <h2>Ranked candidate segments</h2>
      <div class="body" style="padding:0"><table id="cands"><tbody></tbody></table></div>
    </div>
    <div class="card" style="margin-top:14px">
      <h2>History</h2>
      <div class="body hist" style="padding:0"><table id="hist"><tbody></tbody></table></div>
    </div>
  </div>
</div>

<footer id="foot"></footer>
</div>

<script>
/* ===========================================================================
   FOAE live demo.

   THIS FILE DOES NOT ATTRIBUTE ANYTHING. Every verdict, confidence, candidate
   ranking, gate state and abstention reason is precomputed by the Python
   engine and read verbatim out of the run data below. Reimplementing the
   attribution in JS would create a second implementation that drifts from the
   first with nothing to catch it — the exact failure recorded in
   handoff.md section 6. The only logic here is layout and formatting.

   MODE A: fetch demo_runs.json (works when served over http).
   MODE B: fall back to the inlined copy (works from file:// on double-click).
   =========================================================================== */

const INLINE_RUNS = __DATA__;

let RUNS = INLINE_RUNS, SOURCE = "inlined";

/* Segment id -> graph node id. Mirrors the two id rules in
   foae/epdg/graph.py (connector_segment_id / rail_segment_id), inverted.
   Identifier mapping only — no scoring, no ranking. */
function segToNode(seg){
  if(!seg) return null;
  if(seg.startsWith("SEG_CONN_")) return "C_" + seg.slice(9);
  if(seg.startsWith("SEG_RAIL_")){
    const stem = seg.slice(9);
    return stem.startsWith("GND_") ? "SENSOR_" + stem : stem;
  }
  return null;
}
const fmt = v => (v === null || v === undefined) ? "—" : (+v).toFixed(3);
const esc = s => String(s).replace(/[&<>"]/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;"}[c]));

/* ---------------- state ---------------- */
let cur = null, last = -1;
const tally = {n:0, named:0, ok:0, ab:0, bad:0};
const history = [];
const $ = id => document.getElementById(id);

/* ---------------- schematic ---------------- */
const NS = "http://www.w3.org/2000/svg";
function el(t, a){
  const e = document.createElementNS(NS, t);
  for(const k in a) e.setAttribute(k, a[k]);
  return e;
}
function txt(x, y, s, o){
  const t = el("text", Object.assign({x, y, "text-anchor":"middle",
    "font-size":10.5, "font-family":"ui-monospace,Menlo,Consolas,monospace"}, o||{}));
  t.textContent = s;
  return t;
}

function drawSchematic(s){
  const svg = $("sch");
  svg.innerHTML = "";
  const topo = RUNS.topology;
  const sensors = topo.nodes.filter(n => n.kind === "sensor");
  const rails   = topo.nodes.filter(n => n.kind === "rail");
  const connOf  = {};
  topo.edges.forEach(e => {
    const src = topo.nodes.find(n => n.id === e.from);
    if(src && src.kind === "sensor") connOf[e.from] = e.to;
  });

  const anom = new Set(s ? s.observed_anomalous : []);
  const named = s ? s.verdict.segment_id : null;
  const truth = s ? s.ground_truth.segment_id : null;
  const namedCand = s && named ? s.candidates.find(c => c.segment_id === named) : null;
  const fp = new Set(namedCand ? namedCand.footprint : []);
  const namedNode = segToNode(named), truthNode = segToNode(truth);

  const X = {sensor:80, conn:300, rail:520, ecu:690};
  const top = 34, gap = 48;
  const ry = {};
  rails.forEach((r, i) => ry[r.id] = top + 34 + i * 62);

  /* connector -> rail edges first, so boxes paint over them */
  topo.edges.forEach(e => {
    if(!(e.from in ry) && e.rail && ry[e.rail] !== undefined && e.from.startsWith("C_")){
      const si = sensors.findIndex(n => connOf[n.id] === e.from);
      if(si < 0) return;
      const y = top + si * gap, yr = ry[e.rail];
      const on = fp.size && sensors[si] && fp.has(sensors[si].id);
      const mid = (X.conn + 34 + X.rail) / 2;
      svg.appendChild(el("path", {
        d:`M${X.conn+34} ${y} H${mid} V${yr} H${X.rail-38}`, fill:"none",
        stroke: on ? "var(--accent)" : "var(--wire-rail)",
        "stroke-width": on ? 2.4 : 1.1, opacity: on ? 1 : .55}));
    }
  });

  /* rails */
  rails.forEach(r => {
    const y = ry[r.id];
    const isNamed = namedNode === r.id, isTruth = truthNode === r.id;
    const stroke = isNamed ? "var(--accent)" : isTruth ? "var(--fault)" : "var(--wire-rail)";
    svg.appendChild(el("path", {d:`M${X.rail+42} ${y} H${X.ecu-30}`, fill:"none",
      stroke, "stroke-width": isNamed ? 2.6 : 1.4}));
    svg.appendChild(el("rect", {x:X.rail-38, y:y-13, width:80, height:26, rx:3,
      fill: isNamed ? "color-mix(in srgb,var(--accent) 16%,var(--panel))" : "var(--panel)",
      stroke, "stroke-width": isNamed ? 2.4 : 1.3,
      "stroke-dasharray": (isTruth && !isNamed) ? "4 3" : "none"}));
    svg.appendChild(txt(X.rail+2, y+4, r.id.replace("SENSOR_",""),
      {fill: isNamed ? "var(--accent)" : "var(--wire-rail)", "font-size":9.5}));
  });

  /* sensors + connectors */
  sensors.forEach((n, i) => {
    const y = top + i * gap;
    const cid = connOf[n.id];
    const on = anom.has(n.id), inFp = fp.has(n.id);
    const sigCol = on ? "var(--fault)" : "var(--wire-sig)";
    svg.appendChild(el("path", {d:`M${X.sensor+52} ${y} H${X.conn-34}`, fill:"none",
      stroke:sigCol, "stroke-width": on ? 2.4 : 1.1}));

    const isNamedC = namedNode === cid, isTruthC = truthNode === cid;
    const cStroke = isNamedC ? "var(--accent)" : isTruthC ? "var(--fault)"
                  : on ? "var(--fault)" : "var(--rule)";
    svg.appendChild(el("rect", {x:X.conn-34, y:y-12, width:68, height:24, rx:3,
      fill: isNamedC ? "color-mix(in srgb,var(--accent) 16%,var(--panel))" : "var(--panel)",
      stroke:cStroke, "stroke-width": isNamedC ? 2.4 : 1.3,
      "stroke-dasharray": (isTruthC && !isNamedC) ? "4 3" : "none"}));
    svg.appendChild(txt(X.conn, y+4, cid, {fill: isNamedC ? "var(--accent)" : "var(--ink-2)",
      "font-size":9.5}));

    svg.appendChild(el("rect", {x:X.sensor-26, y:y-13, width:78, height:26, rx:3,
      fill: on ? "color-mix(in srgb,var(--fault) 13%,var(--panel))" : "var(--panel)",
      stroke: on ? "var(--fault)" : (inFp ? "var(--accent)" : "var(--rule)"),
      "stroke-width": on ? 2.2 : 1.3}));
    svg.appendChild(txt(X.sensor+13, y+4, n.id.replace(/_/g,"\\u2009"),
      {fill: on ? "var(--fault)" : "var(--ink)", "font-size":9}));
  });

  /* CMV — no Tier-2 connector, straight to the ECU */
  const cmvY = top + sensors.length * gap;
  const cmvOn = anom.has("control_module_voltage");
  svg.appendChild(el("path", {d:`M${X.sensor+52} ${cmvY} H${X.ecu-30}`, fill:"none",
    stroke: cmvOn ? "var(--fault)" : "var(--wire-sig)",
    "stroke-width": cmvOn ? 2.4 : 1.1, "stroke-dasharray":"5 4"}));
  svg.appendChild(el("rect", {x:X.sensor-26, y:cmvY-13, width:78, height:26, rx:3,
    fill: cmvOn ? "color-mix(in srgb,var(--fault) 13%,var(--panel))" : "var(--panel)",
    stroke: cmvOn ? "var(--fault)" : "var(--rule)", "stroke-width": cmvOn ? 2.2 : 1.3}));
  svg.appendChild(txt(X.sensor+13, cmvY+4, "cmv",
    {fill: cmvOn ? "var(--fault)" : "var(--ink-2)", "font-size":9}));
  svg.appendChild(txt(X.sensor+13, cmvY+22, "(no Tier-2 connector)",
    {fill:"var(--ink-2)", "font-size":8}));

  /* ECU */
  svg.appendChild(el("rect", {x:X.ecu-30, y:top-16, width:56, height:262, rx:3,
    fill:"var(--panel-2)", stroke:"var(--ink)", "stroke-width":1.5}));
  const e = txt(X.ecu-2, top+118, "ECU", {"font-size":13, fill:"var(--ink)",
    "font-family":"system-ui,sans-serif", "letter-spacing":".14em"});
  e.setAttribute("transform", `rotate(-90 ${X.ecu-2} ${top+118})`);
  svg.appendChild(e);

  ["Sensors","Connectors","Shared rails"].forEach((t, i) => {
    svg.appendChild(txt([X.sensor+13, X.conn, X.rail+2][i], 322, t.toUpperCase(),
      {fill:"var(--ink-2)", "font-size":9, "font-family":"system-ui,sans-serif",
       "letter-spacing":".12em"}));
  });

  $("sch-note").textContent = !s ? "press inject to begin"
    : named ? `solid blue = named segment (${named}) and its footprint`
            : `abstained — dashed red outline marks the ground-truth segment` +
              (truth ? ` (${truth})` : " (Tier-1, no Tier-2 segment)");
}

/* ---------------- sparkline ---------------- */
function spark(v, nom){
  const w = 196, h = 26;
  const mn = Math.min(...v, nom[0]), mx = Math.max(...v, nom[1]), r = (mx - mn) || 1;
  const pts = v.map((y, i) =>
    `${(i / (v.length - 1) * w).toFixed(1)},${(h - (y - mn) / r * h).toFixed(1)}`).join(" ");
  const y0 = (h - (nom[1] - mn) / r * h).toFixed(1);
  const bh = Math.max(1, ((nom[1] - nom[0]) / r * h)).toFixed(1);
  return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none">
    <rect x="0" y="${y0}" width="${w}" height="${bh}" fill="var(--ok)" opacity=".10"/>
    <polyline points="${pts}" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>`;
}

/* ---------------- render ---------------- */
function render(s){
  drawSchematic(s);
  const anom = new Set(s.observed_anomalous);

  /* PIDs */
  $("pids").innerHTML = Object.entries(s.traces.pids).map(([pid, b]) => {
    const on = anom.has(pid), lastV = b.values[b.values.length - 1];
    const t1 = pid === "control_module_voltage";
    return `<div class="pid${on ? " anom" : ""}">
      <div class="n"><span class="nm">${esc(pid)}</span>
      <span class="vv">${fmt(lastV)}</span></div>
      <div style="color:${on ? "var(--fault)" : "var(--ink-2)"}">${spark(b.values, b.nominal)}</div>
      <div class="n"><span class="${on ? "fl" : "t1"}">${
        on ? "anomalous" : "nominal"}</span><span class="t1">${
        t1 ? "tier 1" : ""}</span></div></div>`;
  }).join("");

  /* verdict */
  const v = s.verdict, t1 = s.tier1;
  const gateCls = t1.gate === "TRIPPED" ? "bad" : t1.gate === "DEGRADED" ? "abst" : "good";
  let head, body;
  if(v.abstained){
    head = `<span class="pill abst">abstained</span>
            <span class="pill ${gateCls}">gate ${esc(t1.gate)}</span>`;
    body = `<div class="seg abst">${esc(v.reason)}</div>`;
  }else{
    head = `<span class="pill ${v.correct ? "good" : "bad"}">${
             v.correct ? "correct" : "misattributed"}</span>
            <span class="pill ${gateCls}">gate ${esc(t1.gate)}</span>`;
    body = `<div class="seg ${v.correct ? "good" : "bad"}">${esc(v.segment_id)}</div>`;
  }
  $("verdict").innerHTML = `<div class="vhead">${head}</div>${body}
    <dl class="kv">
      <dt>injected fault</dt><dd>${esc(s.label)}</dd>
      <dt>ground truth</dt><dd>${esc(s.ground_truth.segment_id || "— (Tier 1)")}</dd>
      <dt>named segment</dt><dd>${esc(v.segment_id || "— declined")}</dd>
      <dt>match score</dt><dd>${fmt(v.confidence)}${
        v.confidence === null ? "" : " <span style=\\"color:var(--ink-2)\\">(uncalibrated)</span>"}</dd>
      <dt>observed anomalous</dt><dd>${s.observed_anomalous.length
        ? esc(s.observed_anomalous.join(", ")) : "none"}</dd>
      <dt>tier-1 confound</dt><dd>${fmt(t1.confound_score)} / thr ${fmt(t1.threshold)}${
        t1.cmv_anomalous ? " · cmv anomalous" : ""}</dd>
      <dt>severity</dt><dd>${fmt(s.ground_truth.severity)} · ${esc(s.ground_truth.fault_type)}</dd>
    </dl>`;

  /* candidates */
  const top = s.candidates.length ? s.candidates[0].match_score : 1;
  $("cands").innerHTML =
    `<thead><tr><th>Segment</th><th class="mono">Score</th><th>Footprint</th></tr></thead><tbody>` +
    s.candidates.slice(0, 6).map(c => {
      const win = c.segment_id === v.segment_id;
      const tr = c.segment_id === s.ground_truth.segment_id;
      const w = top > 0 ? (c.match_score / top * 66).toFixed(0) : 0;
      return `<tr class="${win ? "win " : ""}${tr ? "truth" : ""}">
        <td class="mono">${esc(c.segment_id)}</td>
        <td class="barcell"><i style="width:${w}px"></i><span>${c.match_score.toFixed(3)}</span></td>
        <td class="mono" style="font-size:11px;color:var(--ink-2)">${
          esc(c.footprint.join(", ")) || "—"}</td></tr>`;
    }).join("") + `</tbody>`;

  /* tally */
  tally.n++;
  if(v.abstained) tally.ab++;
  else { tally.named++; v.correct ? tally.ok++ : tally.bad++; }
  $("t-n").textContent = tally.n;
  $("t-named").textContent = tally.named;
  $("t-ok").textContent = tally.ok;
  $("t-ab").textContent = tally.ab;
  $("t-bad").textContent = tally.bad;

  /* history */
  history.unshift({
    truth: s.ground_truth.segment_id || "SEG_OBD_* (tier 1)",
    got: v.abstained ? "ABSTAIN / " + v.reason : v.segment_id,
    cls: v.abstained ? "abst" : (v.correct ? "good" : "bad"),
    score: v.confidence
  });
  if(history.length > 40) history.pop();
  $("hist").innerHTML =
    `<thead><tr><th>Injected</th><th>Verdict</th><th class="mono">Score</th></tr></thead><tbody>` +
    history.map(h => `<tr><td class="mono" style="font-size:11px">${esc(h.truth)}</td>
      <td class="mono ${h.cls}" style="font-size:11px">${esc(h.got)}</td>
      <td class="mono" style="font-size:11px">${fmt(h.score)}</td></tr>`).join("") +
    `</tbody>`;
}

/* Staged loading effect. COSMETIC ONLY: the scenario is already computed and
   sitting in RUNS, and every stage named below ran in Python when demo_runs.json
   was generated. The delay buys nothing and measures nothing - it just makes the
   pipeline legible on the way past. Stage names mirror the real order in
   pipeline.run_scenario(): simulate -> poll -> detect -> gate -> attribute. */
const STAGES = [
  "simulating drive cycle",
  "polling PIDs over OBD-II",
  "detecting anomalies against noise floor",
  "assessing Tier-1 confound gate",
  "scoring EPDG segments"
];
const STAGE_MS = 165;

let busy = false, gen = 0, timers = [];
function clearTimers(){ timers.forEach(clearTimeout); timers = []; }
function later(fn, ms){ timers.push(setTimeout(fn, ms)); }

function paintStages(active){
  $("verdict").innerHTML =
    '<div class="loading"><div class="vhead"><span class="spin"></span>' +
    '<b>Analysing session\u2026</b></div><ul class="stages">' +
    STAGES.map((s, k) => `<li class="${k < active ? "done" : k === active ? "on" : ""}">` +
      esc(s) + '</li>').join("") +
    '</ul></div>';
}

function finish(myGen, scenario){
  if(myGen !== gen) return;              // reset pressed mid-load
  try{
    render(scenario);
  }catch(err){
    $("verdict").innerHTML = '<div class="err">render error: ' +
      esc(err && err.message) + '</div>';
  }finally{
    busy = false;
    $("go").disabled = false;
    $("sch").style.opacity = "";
  }
}

function inject(){
  if(busy) return;
  try{
    const n = RUNS.scenarios.length;
    if(!n){ $("verdict").innerHTML = '<div class="err">No scenarios in run data.</div>'; return; }
    let i = Math.floor(Math.random() * n);
    if(n > 1 && i === last) i = (i + 1 + Math.floor(Math.random() * (n - 1))) % n;
    last = i;
    cur = RUNS.scenarios[i];

    busy = true;
    const myGen = ++gen;
    $("go").disabled = true;
    $("sch").style.opacity = ".35";
    $("sch-note").textContent = "injecting\u2026";

    const reduce = typeof window !== "undefined" && window.matchMedia &&
                   window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const step = reduce ? 0 : STAGE_MS;

    if(!step){ finish(myGen, cur); return; }

    paintStages(0);
    STAGES.forEach((_, k) => {
      if(k > 0) later(() => { if(myGen === gen) paintStages(k); }, k * step);
    });
    later(() => finish(myGen, cur), STAGES.length * step);
  }catch(err){
    busy = false;
    $("go").disabled = false;
    $("sch").style.opacity = "";
    $("verdict").innerHTML = '<div class="err">render error: ' +
      esc(err && err.message) + '</div>';
  }
}

function foot(){
  const m = RUNS.meta || {};
  $("foot").innerHTML =
    `run <code>${esc(m.run_id || "?")}</code> · ${esc(m.scenario_count || (RUNS.scenarios||[]).length)}
     precomputed scenarios · seed <code>${esc(m.seed)}</code> · commit
     <code>${esc(m.commit || "?")}</code> · data source: <b>${esc(SOURCE)}</b><br>
     ${esc(m.selection || "")}<br>${esc(m.trace_note || "")}<br>
     Regenerate: <code>python -m foae.pipeline demo -n 24 --seed 42</code>
     then <code>python docs/demo/build_demo.py</code>.`;
}

/* MODE A: prefer a served demo_runs.json so a regenerated file shows up without
   rebuilding this page. Fails silently on file:// (opaque origin) and MODE B's
   inlined copy stands. */
async function boot(){
  try{
    const res = await fetch("demo_runs.json", {cache:"no-store"});
    if(res && res.ok){
      const j = await res.json();
      if(j && Array.isArray(j.scenarios) && j.scenarios.length){
        RUNS = j; SOURCE = "fetched demo_runs.json";
      }
    }
  }catch(_){ /* file:// — expected; keep the inlined copy */ }
  try{ drawSchematic(null); foot(); }catch(_){}
}

$("go").addEventListener("click", inject);
$("reset").addEventListener("click", () => {
  clearTimers(); gen++; busy = false;
  $("go").disabled = false; $("sch").style.opacity = "";
  tally.n = tally.named = tally.ok = tally.ab = tally.bad = 0;
  history.length = 0;
  ["t-n","t-named","t-ok","t-ab","t-bad"].forEach(k => $(k).textContent = "0");
  $("hist").innerHTML = ""; $("cands").innerHTML = ""; $("pids").innerHTML = "";
  cur = null; last = -1;
  $("verdict").innerHTML = '<span class="sub">No fault injected yet.</span>';
  drawSchematic(null);
});
document.addEventListener("keydown", e => {
  if(e.key === " " || e.key === "Enter"){
    if(document.activeElement && document.activeElement.tagName === "BUTTON") return;
    e.preventDefault(); inject();
  }
});
boot();
</script>
</body>
</html>
"""

OUT.write_text(HTML.replace("__DATA__", blob), encoding="utf-8")
size = OUT.stat().st_size
print(f"wrote {OUT} ({size:,} bytes)")
assert size > 10000, "suspiciously small output"
