import {
  badgeStyle,
  headerText,
  mergeDepartures,
  platformText,
  readStop,
  timeLabel,
  visibleDepartures,
  walkText,
} from './format';
import { strings, type Strings } from './i18n';
import type {
  BadgeKind,
  CardConfig,
  Departure,
  EntityConfig,
  HassEntity,
  HomeAssistant,
  Layout,
  StopView,
  TimeLabel,
  VisibleRow,
} from './types';

const TAG = 'imhd-departures-card';
const TICK_MS = 15_000;
const DEFAULT_ROWS = 3;
const MERGED_ROWS = 6;
const DEFAULT_CLOCK_AFTER = 60;
const DEFAULT_TITLE = 'MHD';
const LIVE_DOT = '#66BB6A';
const DELAY_COLOR = '#FB8C00';

// Every size and color can be changed from outside with the --imhd-* variables (theme or a parent card).
const STYLE = `
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
  .dot { width: var(--imhd-dot-size, 8px); height: var(--imhd-dot-size, 8px); border-radius: 50%; background: var(--imhd-live-color, ${LIVE_DOT}); flex: none; }
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
  .sub .delay { color: var(--imhd-delay-color, ${DELAY_COLOR}); }
  .time { display: flex; align-items: baseline; gap: 5px; white-space: nowrap; flex: none; }
  .minutes { font-size: var(--imhd-minutes-size, 30px); font-weight: var(--imhd-minutes-weight, 200); line-height: 1; }
  .unit { font-size: 13px; color: var(--secondary-text-color); }
  .now { font-size: 17px; }
  .empty, .warning, .stop-status { margin: 10px 0 0; font-size: 15px; color: var(--secondary-text-color); }
  .stop-status + .stop-status { margin-top: 4px; }
`;

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null;

interface RenderContext {
  now: number;
  t: Strings;
  formatTime: (iso: string) => string;
  clockAfter: number;
  timeZone: string | undefined;
  badge: BadgeKind;
}

function timeHtml(label: TimeLabel, t: Strings): string {
  if (label.kind === 'now') return `<span class="now">${escapeHtml(t.now)}</span>`;
  if (label.kind === 'clock') return `<span class="minutes">${escapeHtml(label.value)}</span>`;
  return `<span class="minutes">${label.value}</span><span class="unit">${escapeHtml(t.min)}</span>`;
}

/** Second-line parts (HTML): platform letter when known, the walk time when given, then the delay or the timetable note. */
function subParts(d: Departure, t: Strings, walk: string | null = null): string[] {
  const parts: string[] = [];
  const platform = platformText(d, t);
  if (platform !== null) parts.push(escapeHtml(platform));
  if (walk !== null) parts.push(escapeHtml(walk));
  if (d.realtime && d.delay_min >= 2) parts.push(`<span class="delay">${escapeHtml(t.delay(d.delay_min))}</span>`);
  else if (!d.realtime) parts.push(escapeHtml(t.timetable));
  return parts;
}

function badgeHtml(d: Departure, kind: BadgeKind): string {
  if (kind === 'neutral') return `<span class="badge neutral">${escapeHtml(d.line)}</span>`;
  const badge = badgeStyle(d);
  return `<span class="badge" style="background:${escapeHtml(badge.background)};color:${escapeHtml(badge.color)}">${escapeHtml(d.line)}</span>`;
}

function rowHtml({ departure: d, missed }: VisibleRow, sub: string[], ctx: RenderContext, entityId?: string): string {
  const classes = missed ? ' class="missed"' : '';
  const tap = entityId ? ` data-entity="${escapeHtml(entityId)}" role="button" tabindex="0"` : '';
  const second = sub.length > 0 ? `<span class="sub">${sub.join(' · ')}</span>` : '';
  return [
    `<li${classes}${tap}>`,
    badgeHtml(d, ctx.badge),
    `<span class="dest"><span class="dest-name">${escapeHtml(d.destination)}</span>${second}</span>`,
    `<span class="time">${timeHtml(timeLabel(d.departs_at, ctx.now, ctx.clockAfter, ctx.timeZone), ctx.t)}</span>`,
    '</li>',
  ].join('');
}

function positiveInt(value: unknown, field: string): number {
  if (typeof value !== 'number' || !Number.isInteger(value) || value < 1) {
    throw new Error(`imhd-departures-card: "${field}" must be a whole number ≥ 1`);
  }
  return value;
}

/** Checks the YAML config; throws a readable error. */
function parseConfig(raw: unknown): CardConfig {
  if (!isRecord(raw)) throw new Error('imhd-departures-card: invalid configuration');
  const { type, title, subtitle, rows, layout, clock_after, language, hide_missed, nearest_only, show_walk, badge, entities } =
    raw;
  if (!Array.isArray(entities) || entities.length === 0) {
    throw new Error('imhd-departures-card: "entities" must list at least one sensor');
  }
  const parsed: EntityConfig[] = entities.map((item, index) => {
    if (typeof item === 'string' && item.startsWith('sensor.')) return { entity: item };
    if (isRecord(item) && typeof item['entity'] === 'string' && item['entity'].startsWith('sensor.')) {
      const config: EntityConfig = { entity: item['entity'] };
      if (item['name'] !== undefined) {
        if (typeof item['name'] !== 'string') throw new Error(`imhd-departures-card: entities[${index}].name must be text`);
        config.name = item['name'];
      }
      if (item['rows'] !== undefined) config.rows = positiveInt(item['rows'], `entities[${index}].rows`);
      return config;
    }
    throw new Error(`imhd-departures-card: entities[${index}] must be a sensor entity id`);
  });
  if (title !== undefined && typeof title !== 'string') throw new Error('imhd-departures-card: "title" must be text');
  if (subtitle !== undefined && typeof subtitle !== 'string') throw new Error('imhd-departures-card: "subtitle" must be text');
  if (layout !== undefined && layout !== 'merged' && layout !== 'stack' && layout !== 'columns') {
    throw new Error('imhd-departures-card: "layout" must be merged, stack or columns');
  }
  if (language !== undefined && language !== 'sk' && language !== 'en') {
    throw new Error('imhd-departures-card: "language" must be sk or en');
  }
  if (hide_missed !== undefined && typeof hide_missed !== 'boolean') {
    throw new Error('imhd-departures-card: "hide_missed" must be true or false');
  }
  if (nearest_only !== undefined && typeof nearest_only !== 'boolean') {
    throw new Error('imhd-departures-card: "nearest_only" must be true or false');
  }
  if (show_walk !== undefined && typeof show_walk !== 'boolean') {
    throw new Error('imhd-departures-card: "show_walk" must be true or false');
  }
  if (badge !== undefined && badge !== 'line' && badge !== 'neutral') {
    throw new Error('imhd-departures-card: "badge" must be line or neutral');
  }
  const parsedLayout: Layout = layout ?? 'merged';
  const config: CardConfig = {
    type: typeof type === 'string' ? type : `custom:${TAG}`,
    rows: rows === undefined ? (parsedLayout === 'merged' ? MERGED_ROWS : DEFAULT_ROWS) : positiveInt(rows, 'rows'),
    layout: parsedLayout,
    clock_after: clock_after === undefined ? DEFAULT_CLOCK_AFTER : positiveInt(clock_after, 'clock_after'),
    hide_missed: hide_missed ?? false,
    nearest_only: nearest_only ?? true,
    show_walk: show_walk ?? true,
    badge: badge ?? 'line',
    entities: parsed,
  };
  if (title !== undefined) config.title = title;
  if (subtitle !== undefined) config.subtitle = subtitle;
  if (language !== undefined) config.language = language;
  return config;
}

class ImhdDeparturesCard extends HTMLElement {
  private config: CardConfig | null = null;
  private hassObj: HomeAssistant | null = null;
  private seen = new Map<string, HassEntity | undefined>();
  private timer: ReturnType<typeof setInterval> | null = null;

  constructor() {
    super();
    const root = this.attachShadow({ mode: 'open' });
    root.addEventListener('click', (event) => {
      const target = event.target instanceof Element ? event.target.closest('[data-entity]') : null;
      const entityId = target?.getAttribute('data-entity');
      if (!entityId) return;
      this.dispatchEvent(new CustomEvent('hass-more-info', { detail: { entityId }, bubbles: true, composed: true }));
    });
  }

  static getStubConfig(hass: HomeAssistant): Record<string, unknown> {
    const entities = Object.entries(hass.states)
      .filter(([id, entity]) => id.startsWith('sensor.imhd_') && entity !== undefined && 'stop_id' in entity.attributes)
      .map(([id]) => id);
    return { type: `custom:${TAG}`, entities };
  }

  setConfig(config: unknown): void {
    this.config = parseConfig(config);
    this.seen.clear();
    this.render();
  }

  set hass(hass: HomeAssistant) {
    this.hassObj = hass;
    if (!this.config) return;
    // Re-render only when one of our state objects changed (Home Assistant replaces changed ones).
    const changed = this.config.entities.some((e) => hass.states[e.entity] !== this.seen.get(e.entity));
    if (changed) this.render();
  }

  connectedCallback(): void {
    this.timer ??= setInterval(() => this.render(), TICK_MS);
    this.render();
  }

  disconnectedCallback(): void {
    if (this.timer !== null) clearInterval(this.timer);
    this.timer = null;
  }

  getCardSize(): number {
    const config = this.config;
    if (!config) return 1;
    if (config.layout === 'merged') return Math.max(1, Math.ceil(config.rows * 0.9) + 1);
    const rows = config.entities.reduce((sum, e) => sum + 1 + (e.rows ?? config.rows), 0);
    return Math.max(1, Math.ceil(rows * 0.9) + (config.title ? 1 : 0));
  }

  getGridOptions(): { columns: number; min_columns: number; rows: string } {
    return { columns: 6, min_columns: 4, rows: 'auto' };
  }

  private render(): void {
    const root = this.shadowRoot;
    const config = this.config;
    const hass = this.hassObj;
    if (!root || !config || !hass) return;
    const language = config.language ?? hass.locale?.language ?? hass.language;
    const t = strings(language);
    const timeZone = hass.config?.time_zone;
    const formatTime = (iso: string): string =>
      new Date(iso).toLocaleTimeString(language ?? 'sk', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
        ...(timeZone ? { timeZone } : {}),
      });
    const ctx: RenderContext = { now: Date.now(), t, formatTime, clockAfter: config.clock_after, timeZone, badge: config.badge };
    this.seen = new Map(config.entities.map((e) => [e.entity, hass.states[e.entity]]));

    if (config.layout === 'merged') {
      root.innerHTML = `<style>${STYLE}</style><ha-card>${this.renderMerged(config, hass, ctx)}</ha-card>`;
      return;
    }
    const stops = config.entities.map((e) => {
      const entity = hass.states[e.entity];
      if (!entity) return `<div class="stop"><p class="warning">${escapeHtml(t.missingEntity(e.entity))}</p></div>`;
      return this.renderStop(readStop(entity, e.name), e.rows ?? config.rows, ctx);
    });
    const title = config.title ? `<h1 class="title">${escapeHtml(config.title)}</h1>` : '';
    root.innerHTML = `<style>${STYLE}</style><ha-card>${title}<div class="stops ${config.layout}" style="--imhd-columns:${config.entities.length}">${stops.join('')}</div></ha-card>`;
  }

  /** One list of all stops' departures; a status line under it for every stop that is not live. */
  private renderMerged(config: CardConfig, hass: HomeAssistant, ctx: RenderContext): string {
    const { t } = ctx;
    const views: StopView[] = [];
    const warnings: string[] = [];
    for (const e of config.entities) {
      const entity = hass.states[e.entity];
      if (entity) views.push(readStop(entity, e.name));
      else warnings.push(`<p class="warning">${escapeHtml(t.missingEntity(e.entity))}</p>`);
    }
    const allLive = warnings.length === 0 && views.every((s) => s.status === 'live');
    const head = [
      '<div class="head">',
      `<h1 class="title">${escapeHtml(config.title ?? DEFAULT_TITLE)}</h1>`,
      allLive ? '<span class="dot" aria-hidden="true"></span>' : '',
      config.subtitle ? `<span class="subtitle">${escapeHtml(config.subtitle)}</span>` : '',
      '</div>',
    ].join('');
    const live = views.filter((s) => s.status === 'live');
    const rows = mergeDepartures(live, ctx.now, config.rows, config.hide_missed, config.nearest_only);
    const walks = new Map(live.map((s) => [s.entityId, config.show_walk ? walkText(s.walkMin, t) : null]));
    const items = rows.map((r) =>
      rowHtml(r, [escapeHtml(r.stopName), ...subParts(r.departure, t, walks.get(r.entityId) ?? null)], ctx, r.entityId),
    );
    const list = items.length > 0 ? `<ul>${items.join('')}</ul>` : `<p class="empty">${escapeHtml(t.noDepartures)}</p>`;
    const statuses = views
      .filter((s) => s.status !== 'live')
      .map((s) => {
        const text = headerText(s.status, s.lastLive, t, ctx.formatTime) ?? '';
        return `<p class="stop-status">${escapeHtml(t.stopStatus(s.name, text))}</p>`;
      });
    return `${head}${list}${statuses.join('')}${warnings.join('')}`;
  }

  private renderStop(stop: StopView, rows: number, ctx: RenderContext): string {
    const { now, t, formatTime } = ctx;
    const live = stop.status === 'live';
    const status = headerText(stop.status, stop.lastLive, t, formatTime);
    const header = [
      `<div class="header" data-entity="${escapeHtml(stop.entityId)}" role="button" tabindex="0">`,
      live ? '<span class="dot" aria-hidden="true"></span>' : '',
      `<span class="name">${escapeHtml(stop.name)}</span>`,
      status ? `<span class="status">· ${escapeHtml(status)}</span>` : '',
      stop.walkMin > 0 ? `<span class="walk">${escapeHtml(t.walk(stop.walkMin))}</span>` : '',
      '</div>',
    ].join('');
    if (!live) return `<div class="stop">${header}</div>`;
    const visible = visibleDepartures(stop.departures, now, rows, stop.walkMin, this.config?.hide_missed ?? false);
    if (visible.length === 0) return `<div class="stop">${header}<p class="empty">${escapeHtml(t.noDepartures)}</p></div>`;
    const items = visible.map((row) => rowHtml(row, subParts(row.departure, t), ctx));
    return `<div class="stop">${header}<ul>${items.join('')}</ul></div>`;
  }
}

declare global {
  interface Window {
    customCards?: { type: string; name: string; description?: string; preview?: boolean }[];
  }
}

if (!customElements.get(TAG)) {
  customElements.define(TAG, ImhdDeparturesCard);
  window.customCards = window.customCards ?? [];
  window.customCards.push({
    type: TAG,
    name: 'iMHD odchody',
    description: 'Live departures from imhd.sk',
    preview: true,
  });
}
