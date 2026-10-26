// Shared by the setup sheets and the breakdown page. build.py pastes this file into both.

// [key, F1Laps label, label shown here, game minimum, game maximum]
const FIELDS = [
  ["front_wing", "Front Wing", "Front wing", 0, 50],
  ["rear_wing", "Rear Wing", "Rear wing", 0, 50],
  ["diff_on", "Differential On Throttle", "Differential on throttle", 10, 100],
  ["diff_off", "Differential Off Throttle", "Differential off throttle", 10, 100],
  ["engine_braking", "Engine Braking", "Engine braking", 0, 100],
  ["front_camber", "Front Camber", "Front camber", -3.5, -2.5],
  ["rear_camber", "Rear Camber", "Rear camber", -2.2, -0.7],
  ["front_toe", "Front Toe", "Front toe", 0, 0.5],
  ["rear_toe", "Rear Toe", "Rear toe", 0, 0.5],
  ["front_susp", "Front Suspension", "Front suspension", 1, 41],
  ["rear_susp", "Rear Suspension", "Rear suspension", 1, 41],
  ["front_arb", "Front Anti-Roll Bar", "Front anti-roll bar", 1, 21],
  ["rear_arb", "Rear Anti-Roll Bar", "Rear anti-roll bar", 1, 21],
  ["front_rh", "Front Ride Height", "Front ride height", 10, 40],
  ["rear_rh", "Rear Ride Height", "Rear ride height", 40, 100],
  ["brake_pressure", "Brake Pressure", "Brake pressure", 80, 100],
  ["brake_bias", "Front Brake Bias", "Front brake bias", 50, 70],
  ["fr_pressure", "Front Right Tyre Pressure", "Front right tyre", 22.5, 29.5],
  ["fl_pressure", "Front Left Tyre Pressure", "Front left tyre", 22.5, 29.5],
  ["rr_pressure", "Rear Right Tyre Pressure", "Rear right tyre", 20.5, 26.5],
  ["rl_pressure", "Rear Left Tyre Pressure", "Rear left tyre", 20.5, 26.5],
];
const F = Object.fromEntries(FIELDS.map(([k, src, label, min, max]) => [k, { src, label, min, max }]));
const GROUPS = [
  ["Aerodynamics", ["front_wing", "rear_wing"]],
  ["Transmission", ["diff_on", "diff_off", "engine_braking"]],
  ["Suspension geometry", ["front_camber", "rear_camber", "front_toe", "rear_toe"]],
  ["Suspension", ["front_susp", "rear_susp", "front_arb", "rear_arb", "front_rh", "rear_rh"]],
  ["Brakes", ["brake_pressure", "brake_bias"]],
  ["Tyres", ["fr_pressure", "fl_pressure", "rr_pressure", "rl_pressure"]],
];

function num(v) { return parseFloat(String(v).replace(/[^0-9.\-]/g, "")); }
function values(block) {
  const out = {};
  if (!block) return null;
  for (const [k, f] of Object.entries(F)) if (block[f.src] !== undefined) out[k] = num(block[f.src]);
  return out;
}
function clamp(k, v) { return Math.min(F[k].max, Math.max(F[k].min, v)); }
function round2(v) { return Math.round(v * 100) / 100; }
function fmt(k, v) {
  if (v === undefined || v === null || Number.isNaN(v)) return "—";
  if (k.endsWith("camber") || k.endsWith("toe")) return v.toFixed(2) + "°";
  if (k.startsWith("diff") || k === "engine_braking" || k === "brake_pressure" || k === "brake_bias") return round2(v) + "%";
  if (k.endsWith("pressure")) return round2(v) + `<span class="unit"> psi</span>`;
  return String(round2(v));
}
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]); }

// The value each setting gets on this site. Each sheet has a Race view and a Time Trial view,
// and each view counts only its own pool of up to 100 of the fastest setups (fetch.py's
// one_list() builds it). The vote for a setting is the value most of that pool runs. When F1Laps' median is a value whose share is within 10
// points of the top share (45% against 55%, say), the median wins instead. F1Laps' own value,
// the median of its 100 fastest setups, fills in where the pool has fewer than five setups, or
// where its setup pages leave the setting out (engine braking).
const AGREE = 0.7;
const CLOSE = 0.1;
const VIEWS = [["race", "Race"], ["tt", "Time Trial"]];
function consensus(t, cond, view) {
  const median = values(t[cond]);
  const f = t.fastest && t.fastest[cond] && t.fastest[cond][view];
  const marked = new Set(t.important.map(label => FIELDS.find(x => x[1] === label)?.[0]).filter(Boolean));
  const dry = cond === "dry" && f && f.n >= 5;
  // A setup from fetch.py as a full set of values. Settings its setup pages leave out (engine
  // braking) keep the vote.
  const vote = {}, full = vals => Object.fromEntries(Object.keys(median).map(k => [k, vals[F[k].src] ?? vote[k]]));
  const out = {}, agreed = new Set(), against = new Set(), counted = new Set();
  for (const k of Object.keys(median)) {
    const counts = f && f.n >= 5 && f.counts[F[k].src];
    if (!counts) {
      vote[k] = median[k];
      continue;
    }
    const most = counts[0][1];
    const within = counts.filter(([, c]) => (most - c) / f.n <= CLOSE + 1e-9).map(([v]) => v);
    // An exact tie for the top share, with the median not among them, goes to the tied value
    // closest to the median.
    const tied = counts.filter(([, c]) => c === most).map(([v]) => v);
    vote[k] = within.includes(median[k]) ? median[k]
      : tied.reduce((a, b) => Math.abs(b - median[k]) < Math.abs(a - median[k]) ? b : a);
    counted.add(k);
  }
  // A dry sheet's reference values come from the Popular column, the setup the most different
  // drivers run. Agreed means the reference runs the value at least 70% of the list runs, and
  // against means 70% run another value.
  const pop = dry && f.popular;
  Object.assign(out, pop ? full(pop.values) : vote);
  for (const k of Object.keys(median)) {
    if (!counted.has(k)) { if (marked.has(k)) agreed.add(k); continue; }
    const counts = f.counts[F[k].src];
    if (counts[0][1] / f.n >= AGREE) (out[k] === counts[0][0] ? agreed : against).add(k);
  }
  // The columns, left to right. Each has a key, a heading, its values and fetch.py's record of
  // who runs it and how quick it is. The F1Laps Meta column is the meta page's dry block, the
  // same in both views, and has no such record.
  const cols = [];
  if (dry) {
    if (f.fast) cols.push({ key: "fast", name: "Fast", values: full(f.fast.values), info: f.fast });
    cols.push({ key: "popular", name: "Popular", values: out, info: pop || null });
    if (f.alt) cols.push({ key: "alt", name: "Alt", values: full(f.alt.values), info: f.alt });
    cols.push({ key: "meta", name: "F1Laps Meta", values: median, info: null });
  } else cols.push({ key: "setup", name: "Setup", values: out, info: null });
  return { out, median, agreed, against, counted, cols, n: f ? f.n : 0 };
}

// The Stable column, a recipe built from the F1Laps Meta values. It raises the rear wing 3 clicks,
// lowers the rear anti-roll bar 3 clicks, and fixes the diff, brake pressure and engine braking.
// Front bias moves 1 point forward. A half value rounds to the lower wing, the softer spring and
// anti-roll bar, the higher ride height and the more forward bias. Other settings keep the meta value.
// The F1 26 recipe sets engine braking to 30 and keeps the meta bias, from the author's 2026-car laps.
function stable(median, game) {
  const f126 = game === "f1-26";
  const out = Object.assign({}, median), lim = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  const set = (k, f) => { if (k in out) out[k] = f(median[k]); };
  set("front_wing", Math.floor);
  set("rear_wing", v => lim(Math.floor(v) + 3, 0, 50));
  set("diff_on", () => 75);
  set("diff_off", () => 50);
  set("engine_braking", () => f126 ? 30 : 50);
  set("front_susp", Math.floor);
  set("rear_susp", Math.floor);
  set("front_arb", Math.floor);
  set("rear_arb", v => lim(Math.floor(v) - 3, 1, 21));
  set("front_rh", Math.ceil);
  set("rear_rh", Math.ceil);
  set("brake_pressure", () => 95);
  set("brake_bias", v => Math.ceil(f126 ? v : v + 1));
  return out;
}

// Which F1Laps list a view counts.
function pool(view) { return view === "tt" ? "Time Trial setups" : "race setups"; }

// The chosen track rides in the address (#monaco) and so does the view (?view=tt), so links
// between one game's pages open the same track in the same view. Without either, the page uses
// what this viewer chose last, and then the race view.
function startSlug(fallback) {
  const h = decodeURIComponent(location.hash.slice(1));
  return BY_ID[h] ? h : fallback;
}
function startView(fallback) {
  const v = new URLSearchParams(location.search).get("view");
  return v === "tt" || v === "race" ? v : fallback === "tt" ? "tt" : "race";
}
function keepTrack(slug, view) {
  const q = view === "tt" ? "?view=tt" : "";
  try { history.replaceState(null, "", location.pathname + q + "#" + slug); } catch (e) {}
  for (const a of document.querySelectorAll("a[data-keep]")) a.href = a.dataset.keep + q + "#" + slug;
}
