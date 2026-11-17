const y = {
  tram: "#E53935",
  trolleybus: "#43A047",
  bus: "#1E88E5",
  night: "#37474F",
  neutral: "#616161"
};
function T(t, e) {
  return Math.max(0, Math.ceil((Date.parse(t) - e) / 6e4));
}
function I(t, e, n, s, r) {
  const i = [];
  for (const o of t) {
    const a = Date.parse(o.departs_at);
    if (Number.isNaN(a) || a < e - 3e4) continue;
    const c = T(o.departs_at, e), p = c < s;
    if (!(p && r) && (i.push({ departure: o, minutes: c, missed: p }), i.length >= n))
      break;
  }
  return i;
}
function z(t, e, n, s) {
  const r = T(t, e);
  if (r === 0) return { kind: "now" };
  if (r < n) return { kind: "minutes", value: r };
  const i = new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    ...s ? { timeZone: s } : {}
  }).formatToParts(new Date(t)), o = (a) => i.find((c) => c.type === a)?.value ?? "00";
  return { kind: "clock", value: `${o("hour")}:${o("minute")}` };
}
function _(t) {
  return t.line.toUpperCase() + "|" + (t.terminus ?? t.destination);
}
function S(t, e) {
  const n = new Map(e.map((i) => [i.entityId, i.walkMin])), s = (i) => n.get(i.entityId) ?? 0, r = /* @__PURE__ */ new Map();
  for (const i of t) {
    const o = _(i.departure), a = r.get(o);
    (a === void 0 || s(i) < a) && r.set(o, s(i));
  }
  return t.filter((i) => s(i) === r.get(_(i.departure)));
}
function A(t, e, n, s, r = !1) {
  const i = t.flatMap(
    (a) => I(a.departures, e, Number.POSITIVE_INFINITY, a.walkMin, s).map((c) => ({
      ...c,
      entityId: a.entityId,
      stopName: a.name
    }))
  ), o = r ? S(i, t) : i;
  return o.sort(
    (a, c) => Date.parse(a.departure.departs_at) - Date.parse(c.departure.departs_at) || a.departure.line.localeCompare(c.departure.line, void 0, { numeric: !0 })
  ), o.slice(0, n);
}
function j(t, e) {
  return e.toUpperCase().startsWith("N") ? y.night : t === "tram" ? y.tram : t === "trolleybus" ? y.trolleybus : t === "bus" ? y.bus : y.neutral;
}
function O(t) {
  return { background: t.color ?? j(t.mode, t.line), color: t.text_color ?? "#fff" };
}
function N(t, e) {
  return t.platform_label ? e.platform(t.platform_label) : null;
}
function R(t, e) {
  return t > 0 ? e.walk(t) : null;
}
function k(t, e, n, s) {
  return t === "live" ? null : e ? n.lastLive(s(e)) : t === "connecting" ? n.connecting : n.unavailable;
}
const F = (t) => typeof t == "object" && t !== null;
function H(t) {
  if (!F(t)) return null;
  const { line: e, mode: n, destination: s, departs_at: r, scheduled_at: i, realtime: o, delay_min: a, platform: c } = t, { platform_label: p, color: h, text_color: u, terminus: f } = t, g = (w) => typeof w == "string" && w.trim() !== "" ? w : null;
  return typeof e != "string" || typeof s != "string" || typeof r != "string" ? null : {
    line: e,
    mode: typeof n == "string" ? n : null,
    destination: s,
    terminus: g(f),
    departs_at: r,
    scheduled_at: typeof i == "string" ? i : r,
    realtime: o === !0,
    delay_min: typeof a == "number" ? a : 0,
    platform: typeof c == "number" && Number.isFinite(c) ? c : null,
    platform_label: g(p),
    color: g(h),
    text_color: g(u)
  };
}
function G(t) {
  return t === "live" || t === "connecting" ? t : "unavailable";
}
function P(t, e) {
  return typeof t != "string" || t.trim() === "" ? e : t.replace(/\s+(Odchody|Departures)$/u, "").trim() || t;
}
function E(t, e) {
  const n = t.attributes, s = Array.isArray(n.departures) ? n.departures.map(H) : [];
  return {
    entityId: t.entity_id,
    name: e ?? (typeof n.stop_name == "string" && n.stop_name.trim() !== "" ? n.stop_name : P(n.friendly_name, t.entity_id)),
    status: G(n.status),
    lastLive: typeof n.last_live == "string" ? n.last_live : null,
    walkMin: typeof n.walk_min == "number" ? n.walk_min : 0,
    departures: s.filter((r) => r !== null)
  };
}
const U = {
  walk: (t) => `${t} min pešo`,
  lastLive: (t) => `Naposledy online ${t}`,
  connecting: "Pripája sa…",
  unavailable: "Nedostupné",
  now: "teraz",
  min: "min",
  noDepartures: "Žiadne odchody",
  timetable: "podľa CP",
  delay: (t) => `+${t} min`,
  missingEntity: (t) => `Entita ${t} neexistuje`,
  platform: (t) => "nást. " + t,
  stopStatus: (t, e) => t + ": " + e
}, W = {
  walk: (t) => `${t} min walk`,
  lastLive: (t) => `Last online ${t}`,
  connecting: "Connecting…",
  unavailable: "Unavailable",
  now: "now",
  min: "min",
  noDepartures: "No departures",
  timetable: "timetable",
  delay: (t) => `+${t} min`,
  missingEntity: (t) => `Entity ${t} not found`,
  platform: (t) => "platform " + t,
  stopStatus: (t, e) => t + ": " + e
};
function B(t) {
  return t?.toLowerCase().startsWith("sk") ? U : W;
}
const b = "imhd-departures-card", K = 15e3, Y = 3, V = 6, Z = 60, q = "MHD", J = "#66BB6A", Q = "#FB8C00", D = `
  :host { display: block; }
  ha-card { padding: var(--imhd-card-padding, 16px); background: var(--ha-card-background, var(--card-background-color)); color: var(--primary-text-color); }
  .title { font-size: var(--imhd-title-size, 20px); font-weight: var(--imhd-title-weight, 500); margin: 0 0 12px; }
  .head { display: flex; align-items: center; gap: 8px; margin: 0 0 12px; min-width: 0; }
  .head .title { margin: 0; flex: none; }
  .subtitle { margin-left: auto; font-size: var(--imhd-subtitle-size, 13px); color: var(--secondary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .stops { display: flex; flex-direction: column; gap: 16px; }
  .stops.columns { display: grid; grid-template-columns: repeat(var(--imhd-columns), minmax(0, 1fr)); gap: 16px; }
  .stops.stack > .stop + .stop { border-top: 1px solid var(--divider-color); padding-top: 16px; }
  .header { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 15px; color: var(--secondary-text-color); min-width: 0; }
  .dot { width: var(--imhd-dot-size, 8px); height: var(--imhd-dot-size, 8px); border-radius: 50%; background: var(--imhd-live-color, ${J}); flex: none; }
  .name { color: var(--primary-text-color); font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .status { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .walk { margin-left: auto; white-space: nowrap; flex: none; }
  ul { list-style: none; margin: 10px 0 0; padding: 0; display: flex; flex-direction: column; gap: var(--imhd-list-gap, 8px); }
  li { display: flex; align-items: center; gap: var(--imhd-row-gap, 14px); min-height: 48px; }
  li.missed { opacity: .45; }
  li[data-entity] { cursor: pointer; }
  .badge { display: inline-flex; align-items: center; justify-content: center; box-sizing: border-box; min-width: 44px;
    height: var(--imhd-badge-height, 36px); padding: 0 8px; border-radius: var(--imhd-badge-radius, 10px); color: #fff;
    font-size: var(--imhd-badge-size, 17px); font-weight: 600; flex: none; }
  .badge.neutral { background: var(--imhd-badge-background, var(--secondary-background-color)); color: var(--imhd-badge-color, var(--primary-text-color)); }
  .dest { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .dest-name { font-size: var(--imhd-dest-size, 17px); font-weight: var(--imhd-dest-weight, 400); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .sub { font-size: var(--imhd-sub-size, 13px); color: var(--secondary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .sub .delay { color: var(--imhd-delay-color, ${Q}); }
  .time { display: flex; align-items: baseline; gap: 5px; white-space: nowrap; flex: none; }
  .minutes { font-size: var(--imhd-minutes-size, 30px); font-weight: var(--imhd-minutes-weight, 200); line-height: 1; }
  .unit { font-size: 13px; color: var(--secondary-text-color); }
  .now { font-size: 17px; }
  .empty, .warning, .stop-status { margin: 10px 0 0; font-size: 15px; color: var(--secondary-text-color); }
  .stop-status + .stop-status { margin-top: 4px; }
`;
function d(t) {
  return t.replace(/[&<>"']/g, (e) => `&#${e.charCodeAt(0)};`);
}
const M = (t) => typeof t == "object" && t !== null;
function X(t, e) {
  return t.kind === "now" ? `<span class="now">${d(e.now)}</span>` : t.kind === "clock" ? `<span class="minutes">${d(t.value)}</span>` : `<span class="minutes">${t.value}</span><span class="unit">${d(e.min)}</span>`;
}
function C(t, e, n = null) {
  const s = [], r = N(t, e);
  return r !== null && s.push(d(r)), n !== null && s.push(d(n)), t.realtime && t.delay_min >= 2 ? s.push(`<span class="delay">${d(e.delay(t.delay_min))}</span>`) : t.realtime || s.push(d(e.timetable)), s;
}
function tt(t, e) {
  if (e === "neutral") return `<span class="badge neutral">${d(t.line)}</span>`;
  const n = O(t);
  return `<span class="badge" style="background:${d(n.background)};color:${d(n.color)}">${d(t.line)}</span>`;
}
function L({ departure: t, missed: e }, n, s, r) {
  const i = e ? ' class="missed"' : "", o = r ? ` data-entity="${d(r)}" role="button" tabindex="0"` : "", a = n.length > 0 ? `<span class="sub">${n.join(" · ")}</span>` : "";
  return [
    `<li${i}${o}>`,
    tt(t, s.badge),
    `<span class="dest"><span class="dest-name">${d(t.destination)}</span>${a}</span>`,
    `<span class="time">${X(z(t.departs_at, s.now, s.clockAfter, s.timeZone), s.t)}</span>`,
    "</li>"
  ].join("");
}
function $(t, e) {
  if (typeof t != "number" || !Number.isInteger(t) || t < 1)
    throw new Error(`imhd-departures-card: "${e}" must be a whole number ≥ 1`);
  return t;
}
function et(t) {
  if (!M(t)) throw new Error("imhd-departures-card: invalid configuration");
  const { type: e, title: n, subtitle: s, rows: r, layout: i, clock_after: o, language: a, hide_missed: c, nearest_only: p, show_walk: h, badge: u, entities: f } = t;
  if (!Array.isArray(f) || f.length === 0)
    throw new Error('imhd-departures-card: "entities" must list at least one sensor');
  const g = f.map((m, v) => {
    if (typeof m == "string" && m.startsWith("sensor.")) return { entity: m };
    if (M(m) && typeof m.entity == "string" && m.entity.startsWith("sensor.")) {
      const x = { entity: m.entity };
      if (m.name !== void 0) {
        if (typeof m.name != "string") throw new Error(`imhd-departures-card: entities[${v}].name must be text`);
        x.name = m.name;
      }
      return m.rows !== void 0 && (x.rows = $(m.rows, `entities[${v}].rows`)), x;
    }
    throw new Error(`imhd-departures-card: entities[${v}] must be a sensor entity id`);
  });
  if (n !== void 0 && typeof n != "string") throw new Error('imhd-departures-card: "title" must be text');
  if (s !== void 0 && typeof s != "string") throw new Error('imhd-departures-card: "subtitle" must be text');
  if (i !== void 0 && i !== "merged" && i !== "stack" && i !== "columns")
    throw new Error('imhd-departures-card: "layout" must be merged, stack or columns');
  if (a !== void 0 && a !== "sk" && a !== "en")
    throw new Error('imhd-departures-card: "language" must be sk or en');
  if (c !== void 0 && typeof c != "boolean")
    throw new Error('imhd-departures-card: "hide_missed" must be true or false');
  if (p !== void 0 && typeof p != "boolean")
    throw new Error('imhd-departures-card: "nearest_only" must be true or false');
  if (h !== void 0 && typeof h != "boolean")
    throw new Error('imhd-departures-card: "show_walk" must be true or false');
  if (u !== void 0 && u !== "line" && u !== "neutral")
    throw new Error('imhd-departures-card: "badge" must be line or neutral');
  const w = i ?? "merged", l = {
    type: typeof e == "string" ? e : `custom:${b}`,
    rows: r === void 0 ? w === "merged" ? V : Y : $(r, "rows"),
    layout: w,
    clock_after: o === void 0 ? Z : $(o, "clock_after"),
    hide_missed: c ?? !1,
    nearest_only: p ?? !0,
    show_walk: h ?? !0,
    badge: u ?? "line",
    entities: g
  };
  return n !== void 0 && (l.title = n), s !== void 0 && (l.subtitle = s), a !== void 0 && (l.language = a), l;
}
class nt extends HTMLElement {
  config = null;
  hassObj = null;
  seen = /* @__PURE__ */ new Map();
  timer = null;
  constructor() {
    super(), this.attachShadow({ mode: "open" }).addEventListener("click", (n) => {
      const r = (n.target instanceof Element ? n.target.closest("[data-entity]") : null)?.getAttribute("data-entity");
      r && this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId: r }, bubbles: !0, composed: !0 }));
    });
  }
  static getStubConfig(e) {
    const n = Object.entries(e.states).filter(([s, r]) => s.startsWith("sensor.imhd_") && r !== void 0 && "stop_id" in r.attributes).map(([s]) => s);
    return { type: `custom:${b}`, entities: n };
  }
  setConfig(e) {
    this.config = et(e), this.seen.clear(), this.render();
  }
  set hass(e) {
    if (this.hassObj = e, !this.config) return;
    this.config.entities.some((s) => e.states[s.entity] !== this.seen.get(s.entity)) && this.render();
  }
  connectedCallback() {
    this.timer ??= setInterval(() => this.render(), K), this.render();
  }
  disconnectedCallback() {
    this.timer !== null && clearInterval(this.timer), this.timer = null;
  }
  getCardSize() {
    const e = this.config;
    if (!e) return 1;
    if (e.layout === "merged") return Math.max(1, Math.ceil(e.rows * 0.9) + 1);
    const n = e.entities.reduce((s, r) => s + 1 + (r.rows ?? e.rows), 0);
    return Math.max(1, Math.ceil(n * 0.9) + (e.title ? 1 : 0));
  }
  getGridOptions() {
    return { columns: 6, min_columns: 4, rows: "auto" };
  }
  render() {
    const e = this.shadowRoot, n = this.config, s = this.hassObj;
    if (!e || !n || !s) return;
    const r = n.language ?? s.locale?.language ?? s.language, i = B(r), o = s.config?.time_zone, a = (u) => new Date(u).toLocaleTimeString(r ?? "sk", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: !1,
      ...o ? { timeZone: o } : {}
    }), c = { now: Date.now(), t: i, formatTime: a, clockAfter: n.clock_after, timeZone: o, badge: n.badge };
    if (this.seen = new Map(n.entities.map((u) => [u.entity, s.states[u.entity]])), n.layout === "merged") {
      e.innerHTML = `<style>${D}</style><ha-card>${this.renderMerged(n, s, c)}</ha-card>`;
      return;
    }
    const p = n.entities.map((u) => {
      const f = s.states[u.entity];
      return f ? this.renderStop(E(f, u.name), u.rows ?? n.rows, c) : `<div class="stop"><p class="warning">${d(i.missingEntity(u.entity))}</p></div>`;
    }), h = n.title ? `<h1 class="title">${d(n.title)}</h1>` : "";
    e.innerHTML = `<style>${D}</style><ha-card>${h}<div class="stops ${n.layout}" style="--imhd-columns:${n.entities.length}">${p.join("")}</div></ha-card>`;
  }
  /** One list of all stops' departures; a status line under it for every stop that is not live. */
  renderMerged(e, n, s) {
    const { t: r } = s, i = [], o = [];
    for (const l of e.entities) {
      const m = n.states[l.entity];
      m ? i.push(E(m, l.name)) : o.push(`<p class="warning">${d(r.missingEntity(l.entity))}</p>`);
    }
    const a = o.length === 0 && i.every((l) => l.status === "live"), c = [
      '<div class="head">',
      `<h1 class="title">${d(e.title ?? q)}</h1>`,
      a ? '<span class="dot" aria-hidden="true"></span>' : "",
      e.subtitle ? `<span class="subtitle">${d(e.subtitle)}</span>` : "",
      "</div>"
    ].join(""), p = i.filter((l) => l.status === "live"), h = A(p, s.now, e.rows, e.hide_missed, e.nearest_only), u = new Map(p.map((l) => [l.entityId, e.show_walk ? R(l.walkMin, r) : null])), f = h.map(
      (l) => L(l, [d(l.stopName), ...C(l.departure, r, u.get(l.entityId) ?? null)], s, l.entityId)
    ), g = f.length > 0 ? `<ul>${f.join("")}</ul>` : `<p class="empty">${d(r.noDepartures)}</p>`, w = i.filter((l) => l.status !== "live").map((l) => {
      const m = k(l.status, l.lastLive, r, s.formatTime) ?? "";
      return `<p class="stop-status">${d(r.stopStatus(l.name, m))}</p>`;
    });
    return `${c}${g}${w.join("")}${o.join("")}`;
  }
  renderStop(e, n, s) {
    const { now: r, t: i, formatTime: o } = s, a = e.status === "live", c = k(e.status, e.lastLive, i, o), p = [
      `<div class="header" data-entity="${d(e.entityId)}" role="button" tabindex="0">`,
      a ? '<span class="dot" aria-hidden="true"></span>' : "",
      `<span class="name">${d(e.name)}</span>`,
      c ? `<span class="status">· ${d(c)}</span>` : "",
      e.walkMin > 0 ? `<span class="walk">${d(i.walk(e.walkMin))}</span>` : "",
      "</div>"
    ].join("");
    if (!a) return `<div class="stop">${p}</div>`;
    const h = I(e.departures, r, n, e.walkMin, this.config?.hide_missed ?? !1);
    if (h.length === 0) return `<div class="stop">${p}<p class="empty">${d(i.noDepartures)}</p></div>`;
    const u = h.map((f) => L(f, C(f.departure, i), s));
    return `<div class="stop">${p}<ul>${u.join("")}</ul></div>`;
  }
}
customElements.get(b) || (customElements.define(b, nt), window.customCards = window.customCards ?? [], window.customCards.push({
  type: b,
  name: "iMHD odchody",
  description: "Live departures from imhd.sk",
  preview: !0
}));
