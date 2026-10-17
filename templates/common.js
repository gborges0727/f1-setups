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

// The value each setting gets on this site. A dry sheet uses the most forgiving setup that two
// or more of the fastest share, when there is one. Otherwise the value is the one most of the
// fastest setups F1Laps lists run. When F1Laps' median is a value whose share is within 10 points of the top share (45% against
// 55%, say), the median wins instead. F1Laps' own value, the median of its 100 fastest setups,
// fills in where it lists fewer than five setups, or where its setup pages leave the setting out
// (engine braking).
const AGREE = 0.7;
const CLOSE = 0.1;
function consensus(t, cond) {
  const median = values(t[cond]);
  const f = t.fastest && t.fastest[cond];
  const marked = new Set(t.important.map(label => FIELDS.find(x => x[1] === label)?.[0]).filter(Boolean));
  const out = {}, agreed = new Set(), counted = new Set();
  for (const k of Object.keys(median)) {
    const counts = f && f.n >= 5 && f.counts[F[k].src];
    if (!counts) {
      out[k] = median[k];
      if (marked.has(k)) agreed.add(k);
      continue;
    }
    const most = counts[0][1];
    const within = counts.filter(([, c]) => (most - c) / f.n <= CLOSE + 1e-9).map(([v]) => v);
    // An exact tie for the top share, with the median not among them, goes to the tied value
    // closest to the median.
    const tied = counts.filter(([, c]) => c === most).map(([v]) => v);
    out[k] = within.includes(median[k]) ? median[k]
      : tied.reduce((a, b) => Math.abs(b - median[k]) < Math.abs(a - median[k]) ? b : a);
    // A dry sheet takes every counted setting from the most forgiving setup two or more of the
    // fastest share (fetch.py picks it). Agreed then means the setup runs the value at least
    // 70% of the fastest run.
    const easy = cond === "dry" && f.forgiving ? f.forgiving.values[F[k].src] : undefined;
    if (easy !== undefined) out[k] = easy;
    if (most / f.n >= AGREE && out[k] === counts[0][0]) agreed.add(k);
    counted.add(k);
  }
  // A pick from data/picks.json replaces the sheet's value for that setting. The sheets get
  // picks, and the breakdown pages don't.
  const voted = { ...out }, picked = new Set(), pick = t.pick && t.pick[cond];
  if (pick) for (const [label, v] of Object.entries(pick.values)) {
    const k = FIELDS.find(x => x[1] === label)[0];
    if (out[k] === v) continue;
    out[k] = v;
    picked.add(k);
    agreed.delete(k);
  }
  const forgiving = cond === "dry" && f && f.n >= 5 ? f.forgiving : null;
  // The Fast column: the shared setup with the quickest lap, for drivers who want lap time over
  // ease. Settings its setup pages leave out (engine braking) keep the sheet's value.
  const q = cond === "dry" && f && f.n >= 5 && f.quickest;
  let quick = q ? Object.fromEntries(Object.keys(out).map(k => [k, q.values[F[k].src] ?? out[k]])) : null;
  // When the quickest shared setup is the forgiving one, the Fast column would only repeat it.
  const sameAsMain = !!quick && Object.keys(out).every(k => quick[k] === out[k]);
  if (sameAsMain) quick = null;
  return { out, voted, median, agreed, counted, picked, forgiving, quick, quickInfo: q || null, sameAsMain,
    why: pick ? pick.why : "", n: f ? f.n : 0 };
}

// The chosen track rides in the address (#monaco), so links between one game's pages open the same track.
// Which F1Laps lists a track's counts come from. Data fetched before the switch to qualifying and
// race setups has no "race" count and came from the Time Trial list.
function pool(f) { return f && f.race === undefined ? "Time Trial setups" : "qualifying and race setups"; }

function startSlug(fallback) {
  const h = decodeURIComponent(location.hash.slice(1));
  return BY_ID[h] ? h : fallback;
}
function keepTrack(slug) {
  try { history.replaceState(null, "", "#" + slug); } catch (e) {}
  for (const a of document.querySelectorAll("a[data-keep]")) a.href = a.dataset.keep + "#" + slug;
}
