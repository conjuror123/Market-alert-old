"""The dashboard: one static page from tools/measure.py's numbers, with the history of
earlier measurements so a change shows against the one before it.

    PYTHONPATH=. python -m tools.dashboard MEASURE.json OUT_DIR [--history HISTORY.json]

Writes OUT_DIR/index.html (self-contained: the numbers ride in the page, no outside
code), OUT_DIR/latest.json (the measurement) and OUT_DIR/history.json (the earlier rows
with this one's added; a re-run of the same commit replaces its row). The workflow
(.github/workflows/measure.yml) reads the published history.json back before it builds,
so the history lives on the site, not in the repository.
"""
from __future__ import annotations

import argparse
import json
import os

from tools.measure import headline

HISTORY_KEEP = 200


def with_history(history: "list[dict]", result: dict) -> "list[dict]":
    """The history with this measurement's row last; a row for the same commit and
    window is replaced rather than repeated."""
    row = headline(result)
    kept = [h for h in history
            if not (h.get("commit") == row["commit"] and h.get("window") == row["window"])]
    return (kept + [row])[-HISTORY_KEEP:]


def render(result: dict, history: "list[dict]") -> str:
    payload = json.dumps({"m": result, "h": history}, separators=(",", ":"), default=int)
    payload = payload.replace("</", "<\\/")
    return PAGE.replace("__PAYLOAD__", payload)


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("measure")
    parser.add_argument("out_dir")
    parser.add_argument("--history", default=None,
                        help="the published history.json; none or unreadable starts afresh")
    args = parser.parse_args(argv)
    with open(args.measure, encoding="utf-8") as f:
        result = json.load(f)
    history: "list[dict]" = []
    if args.history and os.path.exists(args.history):
        try:
            with open(args.history, encoding="utf-8") as f:
                loaded = json.load(f)
            history = loaded if isinstance(loaded, list) else []
        except (OSError, ValueError):
            history = []
    history = with_history(history, result)
    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(render(result, history))
    with open(os.path.join(args.out_dir, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, default=int)
    with open(os.path.join(args.out_dir, "history.json"), "w", encoding="utf-8") as f:
        json.dump(history, f, indent=1)
    print(f"wrote {args.out_dir}/index.html with {len(history)} measurement(s) in its history")
    return 0


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jump measured</title>
<style>
:root{
  color-scheme:light;
  --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --ring:rgba(11,11,11,.10); --series:#2a78d6;
  --good:#0ca30c; --critical:#d03b3b; --up:#006300; --wash:#2a78d614;
}
@media (prefers-color-scheme:dark){
  :root:where(:not([data-theme="light"])){
    color-scheme:dark;
    --page:#0d0d0d; --surface:#1a1a19; --ink:#f0efec; --ink2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.10); --series:#3987e5;
    --up:#0ca30c; --wash:#3987e51f;
  }
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --page:#0d0d0d; --surface:#1a1a19; --ink:#f0efec; --ink2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.10); --series:#3987e5;
  --up:#0ca30c; --wash:#3987e51f;
}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink2);
  font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:0 16px 64px}
header{padding:32px 0 8px}
h1{margin:0;color:var(--ink);font-size:clamp(1.6rem,4vw,2.2rem);letter-spacing:-.02em}
h2{margin:0 0 4px;color:var(--ink);font-size:1.2rem}
h3{margin:0 0 6px;color:var(--ink);font-size:.95rem}
p{margin:0}
.meta{color:var(--muted);font-size:.84rem;margin-top:6px}
.meta b{color:var(--ink2);font-weight:600}
a{color:var(--series)}
section{margin-top:40px}
.note{color:var(--muted);font-size:.85rem;max-width:80ch;margin-bottom:12px}
.panel{background:var(--surface);border:1px solid var(--ring);border-radius:6px;padding:16px}
.tiles{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));margin-top:20px}
.tile .k{color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.06em}
.tile .v{color:var(--ink);font-size:2rem;font-weight:700;line-height:1.15;margin-top:4px}
.tile .w{color:var(--muted);font-size:.82rem;margin-top:4px}
.tile .d{font-size:.82rem;margin-top:2px;color:var(--ink2)}
.status{display:inline-flex;gap:6px;align-items:center;font-weight:600}
.status.ok{color:var(--good)} .status.bad{color:var(--critical)}
details{margin-top:8px} summary{cursor:pointer;color:var(--ink2);font-size:.85rem}
.ctl{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:10px}
.ctl label{font-size:.82rem;color:var(--muted)}
select,input{font:inherit;font-size:.85rem;color:var(--ink);background:var(--surface);
  border:1px solid var(--ring);border-radius:4px;padding:5px 8px}
.tablebox{overflow-x:auto;background:var(--surface);border:1px solid var(--ring);border-radius:6px}
table{border-collapse:collapse;width:100%;font-size:.86rem;min-width:520px}
th,td{padding:6px 10px;border-bottom:1px solid var(--grid);text-align:left;white-space:nowrap}
th{position:sticky;top:0;background:var(--surface);color:var(--muted);font-weight:600;
  font-size:.74rem;text-transform:uppercase;letter-spacing:.04em}
th.s{cursor:pointer} th.s:hover{color:var(--ink)}
th[data-dir="-1"]::after{content:" ↓"} th[data-dir="1"]::after{content:" ↑"}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
td.name{color:var(--ink)}
tbody tr:hover td{background:var(--wash)}
tbody tr:last-child td{border-bottom:0}
caption{caption-side:bottom;text-align:left;padding:8px 10px;color:var(--muted);font-size:.8rem}
.chart{position:relative}
.chart svg{display:block;width:100%;height:auto;overflow:visible}
.chart text{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}
.chart .grid{stroke:var(--grid);stroke-width:1}
.chart .base{stroke:var(--axis);stroke-width:1}
.chart .bar{fill:var(--series)}
.chart .bar:hover,.chart .bar.on{opacity:.75}
.chart .line{fill:none;stroke:var(--series);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.chart .dot{fill:var(--series);stroke:var(--surface);stroke-width:2}
.chart .hit{fill:transparent;cursor:crosshair}
#tip{position:fixed;pointer-events:none;z-index:10;background:var(--surface);color:var(--ink);
  border:1px solid var(--ring);border-radius:4px;padding:6px 8px;font-size:.78rem;
  box-shadow:0 4px 16px rgba(0,0,0,.12);opacity:0;white-space:nowrap}
.grid2{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}
footer{margin-top:48px;color:var(--muted);font-size:.82rem;max-width:90ch}
.theme{float:right;margin-top:4px}
</style>
</head>
<body>
<div class="wrap">
<header>
  <select class="theme" id="theme" aria-label="Theme">
    <option value="">system theme</option><option value="light">light</option><option value="dark">dark</option>
  </select>
  <h1>Jump, measured</h1>
  <p class="meta" id="meta"></p>
  <p class="meta" id="meta2"></p>
  <p class="meta" id="checks"></p>
  <div class="tiles" id="tiles"></div>
</header>

<section id="history">
  <h2>Across changes</h2>
  <p class="note">Pushes a week as the bot scores it, one point per measured change, over
  the year named in each row. Runs in the same month share their window, so they differ
  only by the code.</p>
  <div class="panel chart" id="c-history"></div>
  <div class="tablebox" style="margin-top:12px"><table id="t-history"></table></div>
</section>

<section id="volume">
  <h2>Volume</h2>
  <p class="note">An event is an instrument's flags inside 24 hours from its first, worded by
  its rarest; it counts in the window its first reading was found in. A push rings at once;
  a note row goes into the weekly note. <b>As the bot scores it</b>: the sources' record
  applied (a move voted not real left out, a first hour voted overnight moved into its
  night). <b>Detector alone</b>: no record.</p>
  <div class="tablebox"><table id="t-volume"></table></div>
</section>

<section id="split">
  <h2>By block and by instrument</h2>
  <div class="ctl">
    <label for="reading">Reading</label>
    <select id="reading"><option value="bot">as the bot scores it</option>
      <option value="detector">detector alone</option></select>
    <label for="search">Instrument</label>
    <input id="search" type="search" placeholder="filter">
    <select id="block" aria-label="Block"><option value="">all blocks</option></select>
  </div>
  <div class="tablebox"><table id="t-block"></table></div>
  <div class="tablebox" style="margin-top:12px"><table id="t-inst"></table></div>
</section>

<section id="archive">
  <h2>The whole archive, by year</h2>
  <p class="note">Every year since the first stored bar, scored as today's code scores it.
  Instruments start in different years, so each year names the instrument-years it rests
  on; compare years by events per instrument-year. The last year is partial.</p>
  <div class="panel chart" id="c-archive"></div>
  <div class="tablebox" style="margin-top:12px"><table id="t-archive"></table></div>
</section>

<section id="votes">
  <h2>The record's votes, by year</h2>
  <p class="note">Voters reach back different distances, so only some years were ever
  voted: each row is the record's verdicts on moves of that year (the basket's instruments)
  and how many of the year's events, by their biggest reading, carry one.</p>
  <div class="tablebox"><table id="t-votes"></table></div>
</section>

<section id="biggest">
  <div class="grid2">
    <div>
      <h2>The biggest hours of each record</h2>
      <p class="note">Each instrument's top 0.01% of settled hours by size of move, and the word
      the detector alone gave each - the hours nobody would want missed.</p>
      <div class="tablebox"><table id="t-big"></table></div>
    </div>
    <div>
      <h2>Checks</h2>
      <p class="note">The page's own counts, added across: a check that fails stops the
      page from being published.</p>
      <div class="tablebox"><table id="t-checks"></table></div>
    </div>
  </div>
</section>

<section id="coverage">
  <h2>Coverage</h2>
  <div class="tablebox"><table id="t-cover"></table></div>
</section>

<footer>Measured by <code>tools/measure.py</code> (the metrics built cold by
<code>jump.pipeline</code>, scored by <code>jump.jumps.run</code>, a push by
<code>routing.PUSH_TIERS</code>) and drawn by <code>tools/dashboard.py</code>, from the
bar store and the vote record as they were at the measured commit. The bot reads none of
it.</footer>
</div>
<div id="tip" role="status" aria-live="polite"></div>
<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
(function(){
const P = JSON.parse(document.getElementById("payload").textContent);
const M = P.m, H = P.h || [];
const WORDS = ["noticeable","high","major","extreme"];
const W = M.windows.map(w => w.name);
const $ = id => document.getElementById(id);
const fmt = (n, d=0) => n == null ? "—" : Number(n).toLocaleString("en-US",
  {minimumFractionDigits:d, maximumFractionDigits:d});
const n0 = v => fmt(v);
const day = t => t == null ? "—" : new Date(t*1000).toISOString().slice(0,10);
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const repo = "https://github.com/conjuror123/Market-alert";

// theme
const th = $("theme");
try { th.value = localStorage.getItem("theme") || ""; } catch(e) {}
const setTheme = v => { if (v) document.documentElement.dataset.theme = v;
  else delete document.documentElement.dataset.theme; };
setTheme(th.value);
th.onchange = () => { setTheme(th.value); try { localStorage.setItem("theme", th.value); } catch(e) {} };

// header
const meta = M.meta;
$("meta").innerHTML = `Commit <a href="${repo}/commit/${esc(meta.commit)}"><b>${esc(String(meta.commit).slice(0,7))}</b></a>
  on ${esc(meta.branch)} · ${esc(meta.subject)} · measured ${esc(meta.measured_at)}`;
$("meta2").innerHTML = `<b>${meta.instruments}</b> instruments · levels <b>${meta.levels.join(" / ")}σ</b>
  · pushed: ${esc(meta.push_words.join(", "))} · half-year window ${meta.window_days} days
  · bars to ${day(meta.last_bar)} · record ${fmt(meta.record_rows)} votes, newest ${day(meta.record_newest_check)}`;
const failed = M.checks.filter(c => !c.ok);
$("checks").innerHTML = failed.length
  ? `<span class="status bad">✕ ${failed.length} of ${M.checks.length} checks failed</span>`
  : `<span class="status ok">✓ ${M.checks.length} of ${M.checks.length} checks held</span>`;

// tiles: as the bot, the latest year, against the year before and the previous change
const vb = M.volume.bot;
const prev = H.length > 1 ? H[H.length-2] : null;
function delta(now, was, d=2){
  if (was == null) return "";
  const x = now - was;
  if (Math.abs(x) < Math.pow(10,-d)/2) return "no change since the previous measurement";
  return `${x > 0 ? "▲ +" : "▼ "}${fmt(x,d)} since ${esc(String(prev.commit).slice(0,7))}`;
}
const tiles = [
  ["Pushes a week", fmt(vb[W[0]].pushes_a_week,2), `${W[0]} · year before ${fmt(vb[W[1]].pushes_a_week,2)}`,
   prev ? delta(vb[W[0]].pushes_a_week, prev.pushes_a_week) : ""],
  ["Note rows a week", fmt(vb[W[0]].rows_a_week,2), `${W[0]} · year before ${fmt(vb[W[1]].rows_a_week,2)}`,
   prev ? delta(vb[W[0]].rows_a_week, prev.rows_a_week) : ""],
  ["Busiest week's pushes", fmt(vb[W[0]].busiest_week.pushes), `week to ${vb[W[0]].busiest_week.week_to} · year before ${fmt(vb[W[1]].busiest_week.pushes)} (week to ${vb[W[1]].busiest_week.week_to})`,
   prev ? delta(vb[W[0]].busiest_week.pushes, prev.busiest_week, 0) : ""],
  ["Events in the archive", fmt(M.events.bot), `as the bot · detector alone ${fmt(M.events.detector)}`, ""],
];
$("tiles").innerHTML = tiles.map(t => `<div class="panel tile"><div class="k">${t[0]}</div>
  <div class="v">${t[1]}</div><div class="w">${t[2]}</div>${t[3] ? `<div class="d">${t[3]}</div>` : ""}</div>`).join("");

// tooltip
const tip = $("tip");
function showTip(html, ev){ tip.innerHTML = html; tip.style.opacity = 1;
  const x = Math.min(ev.clientX + 12, innerWidth - tip.offsetWidth - 8);
  tip.style.left = x + "px"; tip.style.top = (ev.clientY + 14) + "px"; }
function hideTip(){ tip.style.opacity = 0; }

// a sortable table from column specs: [key, label, numeric, render]
function table(el, cols, rows, caption){
  let key = null, dir = -1;
  function draw(){
    const r = rows.slice();
    if (key){ const c = cols.find(c => c[0] === key);
      r.sort((a,b) => { const x = a[key], y = b[key];
        return (c[2] ? ((x ?? -1e18) - (y ?? -1e18)) : String(x).localeCompare(String(y))) * dir; }); }
    el.innerHTML = `<thead><tr>${cols.map(c => `<th class="s${c[2] ? " n" : ""}" data-k="${c[0]}"
      ${key === c[0] ? `data-dir="${dir}"` : ""}>${c[1]}</th>`).join("")}</tr></thead>
      <tbody>${r.map(row => `<tr>${cols.map((c,i) => `<td class="${c[2] ? "n" : ""}${i === 0 ? " name" : ""}">${
        c[3] ? c[3](row[c[0]], row) : esc(row[c[0]])}</td>`).join("")}</tr>`).join("")}</tbody>
      ${caption ? `<caption>${caption}</caption>` : ""}`;
    el.querySelectorAll("th.s").forEach(h => h.onclick = () => {
      dir = key === h.dataset.k ? -dir : -1; key = h.dataset.k; draw(); });
  }
  draw();
}

// history
table($("t-history"),
  [["measured_at","Measured"],["commit","Commit",false,v => `<a href="${repo}/commit/${esc(v)}">${esc(String(v).slice(0,7))}</a>`],
   ["subject","Change"],["window","Window"],["pushes_a_week","Pushes a week",true,v => fmt(v,2)],
   ["rows_a_week","Rows a week",true,v => fmt(v,2)],["busiest_week","Busiest week",true,v => fmt(v)],
   ["instruments","Instruments",true],["levels","Levels",false,v => esc((v||[]).join(" / "))]],
  H.slice().reverse(), "As the bot scores it. The newest first.");
lineChart($("c-history"), H.map((h,i) => ({x:i, y:h.pushes_a_week,
  tip:`<b>${esc(String(h.commit).slice(0,7))}</b> ${esc(h.subject)}<br>${fmt(h.pushes_a_week,2)} pushes a week · ${esc(h.window)}`})),
  "pushes a week");

// volume
const vrows = [];
for (const r of ["bot","detector"]) for (const w of W){
  const v = M.volume[r][w];
  vrows.push({reading: r === "bot" ? "as the bot" : "detector alone", window: w,
    pushes: v.pushes, rows: v.rows, pw: v.pushes_a_week, rw: v.rows_a_week,
    busiest: v.busiest_week.pushes, bweek: v.busiest_week.week_to, ...v.by_word});
}
table($("t-volume"),
  [["reading","Reading"],["window","Window"],["pushes","Pushes",true,n0],["pw","a week",true,v => fmt(v,2)],
   ["rows","Note rows",true,n0],["rw","a week",true,v => fmt(v,2)],
   ["busiest","Busiest week",true,(v,r) => `${fmt(v)} <span style="color:var(--muted)">to ${r.bweek}</span>`],
   ...WORDS.map(w => [w, w, true, n0])], vrows,
  "Pushes are the events worded " + esc(M.meta.push_words.join(", ")) + "; note rows the rest. Busiest week: Saturday to Friday, by when each event started.");

// block and instrument tables, for the chosen reading
const cover = M.coverage, byT = Object.fromEntries(cover.map(c => [c.ticker, c]));
const blocks = [...new Set(cover.map(c => c.block))].sort();
$("block").innerHTML += blocks.map(b => `<option>${esc(b)}</option>`).join("");
function splits(){
  const r = $("reading").value, q = $("search").value.trim().toLowerCase(), b = $("block").value;
  const brows = blocks.map(bl => { const row = {block: bl, members: cover.filter(c => c.block === bl).length};
    W.forEach((w,i) => { const x = M.by_block[r][w][bl] || {pushes:0, rows:0};
      row["p"+i] = x.pushes; row["r"+i] = x.rows; }); return row; });
  table($("t-block"), [["block","Block"],["members","Instruments",true],
    ...W.flatMap((w,i) => [["p"+i, "Pushes, "+w, true, n0], ["r"+i, "Rows, "+w, true, n0]])], brows);
  const irows = cover.filter(c => (!b || c.block === b) &&
      (!q || (c.ticker + " " + (c.display||"") + " " + c.label).toLowerCase().includes(q)))
    .map(c => { const row = {ticker: c.ticker, name: c.display || c.label, block: c.block,
      provider: c.provider, first: c.first};
      W.forEach((w,i) => { const x = M.by_instrument[r][w][c.ticker] || {pushes:0, rows:0};
        row["p"+i] = x.pushes; row["r"+i] = x.rows; }); return row; });
  table($("t-inst"), [["ticker","Instrument"],["name","Name"],["block","Block"],["provider","Feed"],
    ...W.flatMap((w,i) => [["p"+i, "Pushes, "+w, true, n0], ["r"+i, "Rows, "+w, true, n0]]),
    ["first","History from",true,day]], irows,
    `${irows.length} of ${cover.length} instruments. An instrument whose history starts inside a window counts only the part it had.`);
  archive(r);
}
["reading","search","block"].forEach(id => $(id).addEventListener("input", splits));

// archive
function archive(r){
  const rows = M.archive.filter(y => y.instrument_years >= 0.1).map(y => ({year: y.year + (y.partial ? " (to " + day(M.meta.end - 1) + ")" : ""),
    iy: y.instrument_years, events: y[r].events, pushes: y[r].pushes,
    epi: y.instrument_years ? y[r].events / y.instrument_years : null,
    ppi: y.instrument_years ? y[r].pushes / y.instrument_years : null, y: y.year}));
  barChart($("c-archive"), rows.map(x => ({label: String(x.y), y: x.ppi,
    tip: `<b>${x.year}</b><br>${fmt(x.pushes)} pushes, ${fmt(x.events)} events<br>${fmt(x.iy,1)} instrument-years<br>${fmt(x.ppi,2)} pushes per instrument-year`})),
    "pushes per instrument-year, " + ($("reading").value === "bot" ? "as the bot scores it" : "detector alone"));
  table($("t-archive"), [["year","Year"],["iy","Instrument-years",true,v => fmt(v,1)],
    ["events","Events",true,n0],["pushes","Pushes",true,n0],
    ["epi","Events per instrument-year",true,v => fmt(v,2)],["ppi","Pushes per instrument-year",true,v => fmt(v,2)]],
    rows, "Instrument-years: the years of history the basket's instruments had in that year, summed.");
}

// votes
table($("t-votes"), [["year","Year"],["real","Real",true],["uncertain","Uncertain",true],
  ["not_real","Not real",true],["overnight","Overnight",true],["events","Events",true],
  ["events_voted","Events with a vote",true]], M.votes_by_year.slice().reverse(),
  "The record kept: every verdict on a move not real or overnight, the others for its keep days.");

// biggest hours
const big = M.biggest_hours;
table($("t-big"), [["word","Word"],["hours","Hours",true]],
  [...WORDS, "not flagged"].map(w => ({word: w, hours: big.by_word[w]})),
  `${fmt(big.total)} hours across ${big.by_instrument.length} instruments.`);

// checks
table($("t-checks"), [["ok","",false,v => v ? '<span class="status ok">✓ held</span>' : '<span class="status bad">✕ failed</span>'],
  ["name","Check"],["detail","Compared"]], M.checks);

// coverage
table($("t-cover"), [["ticker","Instrument"],["name","Name"],["block","Block"],["provider","Feed"],
  ["first","First bar",true,day],["last","Last bar",true,day],["years","Years",true,v => fmt(v,1)],["hours","Hours",true,n0]],
  cover.map(c => ({ticker: c.ticker, name: c.display || c.label, block: c.block, provider: c.provider,
    first: c.first, last: c.last, hours: c.hours, years: c.first ? (c.last - c.first) / 31557600 : null})));

splits();

// charts: one series each, thin marks, a tooltip on hover
function frame(el, n){
  const w = 1100, h = 260, l = 44, r = 12, t = 14, b = 28;
  return {w, h, l, r, t, b, iw: w - l - r, ih: h - t - b};
}
function niceMax(v){ if (!(v > 0)) return 1; const p = Math.pow(10, Math.floor(Math.log10(v)));
  for (const m of [1,2,2.5,5,10]) if (v <= m*p) return m*p; return 10*p; }
function axes(f, max, label){
  let s = "";
  for (let i = 0; i <= 4; i++){ const y = f.t + f.ih - f.ih*i/4;
    s += `<line class="grid" x1="${f.l}" x2="${f.w - f.r}" y1="${y}" y2="${y}"/>
      <text x="${f.l - 6}" y="${y + 4}" text-anchor="end">${fmt(max*i/4, max < 4 ? 1 : 0)}</text>`; }
  s += `<line class="base" x1="${f.l}" x2="${f.w - f.r}" y1="${f.t + f.ih}" y2="${f.t + f.ih}"/>`;
  s += `<text x="${f.l}" y="${f.t - 2}">${esc(label)}</text>`;
  return s;
}
function barChart(el, pts, label){
  const f = frame(el, pts.length), max = niceMax(Math.max(...pts.map(p => p.y || 0)));
  const band = f.iw / Math.max(pts.length, 1), bw = Math.min(24, band - 2);
  let s = axes(f, max, label);
  pts.forEach((p, i) => { const x = f.l + i*band + (band - bw)/2, hh = (p.y || 0) / max * f.ih;
    const y = f.t + f.ih - hh, rr = Math.min(4, hh);
    s += `<path class="bar" d="M${x},${f.t + f.ih} V${y + rr} Q${x},${y} ${x + rr},${y} H${x + bw - rr} Q${x + bw},${y} ${x + bw},${y + rr} V${f.t + f.ih} Z"/>`;
    const tick = pts.length > 12 ? "’" + p.label.slice(-2) : p.label;
    if (pts.length <= 30 || i % 2 === 0) s += `<text x="${x + bw/2}" y="${f.h - 8}" text-anchor="middle">${esc(tick)}</text>`;
    s += `<rect class="hit" data-i="${i}" x="${f.l + i*band}" y="${f.t}" width="${band}" height="${f.ih}"/>`; });
  el.innerHTML = `<svg viewBox="0 0 ${f.w} ${f.h}" role="img" aria-label="${esc(label)}">${s}</svg>`;
  el.querySelectorAll(".hit").forEach(h => { const p = pts[+h.dataset.i];
    h.onmousemove = e => showTip(p.tip, e); h.onmouseleave = hideTip; });
}
function lineChart(el, pts, label){
  const f = frame(el, pts.length), max = niceMax(Math.max(...pts.map(p => p.y || 0)) * 1.15);
  const n = Math.max(pts.length - 1, 1), X = i => f.l + (pts.length === 1 ? f.iw/2 : f.iw*i/n);
  const Y = v => f.t + f.ih - (v || 0)/max*f.ih;
  let s = axes(f, max, label);
  if (pts.length > 1) s += `<path class="line" d="${pts.map((p,i) => (i ? "L" : "M") + X(i) + "," + Y(p.y)).join(" ")}"/>`;
  pts.forEach((p,i) => { s += `<circle class="dot" cx="${X(i)}" cy="${Y(p.y)}" r="5"/>`;
    const hw = pts.length === 1 ? f.iw : f.iw/n;
    s += `<rect class="hit" data-i="${i}" x="${X(i) - hw/2}" y="${f.t}" width="${hw}" height="${f.ih}"/>`; });
  el.innerHTML = `<svg viewBox="0 0 ${f.w} ${f.h}" role="img" aria-label="${esc(label)}">${s}</svg>`;
  el.querySelectorAll(".hit").forEach(h => { const p = pts[+h.dataset.i];
    h.onmousemove = e => showTip(p.tip, e); h.onmouseleave = hideTip; });
}
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
