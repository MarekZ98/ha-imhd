import type { Strings } from './i18n';
import type { Departure, HassEntity, MergedRow, Status, StopView, TimeLabel, VisibleRow } from './types';

/** A vehicle stays on the board this long after its departure time. */
export const DEPARTED_GRACE_MS = 30_000;

export const BADGE_COLORS = {
  tram: '#E53935',
  trolleybus: '#43A047',
  bus: '#1E88E5',
  night: '#37474F',
  neutral: '#616161',
} as const;

/** Whole minutes until `departsAt`, rounded up; 0 = leaving now. */
export function minutesUntil(departsAt: string, now: number): number {
  return Math.max(0, Math.ceil((Date.parse(departsAt) - now) / 60_000));
}

/** Departed rows dropped, rows you cannot catch marked (or hidden), at most `rows`. */
export function visibleDepartures(
  departures: readonly Departure[],
  now: number,
  rows: number,
  walkMin: number,
  hideMissed: boolean,
): VisibleRow[] {
  const result: VisibleRow[] = [];
  for (const departure of departures) {
    const at = Date.parse(departure.departs_at);
    if (Number.isNaN(at) || at < now - DEPARTED_GRACE_MS) continue;
    const minutes = minutesUntil(departure.departs_at, now);
    const missed = minutes < walkMin;
    if (missed && hideMissed) continue;
    result.push({ departure, minutes, missed });
    if (result.length >= rows) break;
  }
  return result;
}

/** "teraz" at 0, "N min" below `clockAfter`, else the clock time HH:MM (24 h) in `timeZone`. */
export function timeLabel(departsAt: string, now: number, clockAfter: number, timeZone?: string): TimeLabel {
  const minutes = minutesUntil(departsAt, now);
  if (minutes === 0) return { kind: 'now' };
  if (minutes < clockAfter) return { kind: 'minutes', value: minutes };
  const parts = new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    ...(timeZone ? { timeZone } : {}),
  }).formatToParts(new Date(departsAt));
  const part = (type: string): string => parts.find((p) => p.type === type)?.value ?? '00';
  return { kind: 'clock', value: `${part('hour')}:${part('minute')}` };
}

/** One line + direction: the line (case-insensitive) and the terminus, else the destination. */
export function directionKey(d: Pick<Departure, 'line' | 'terminus' | 'destination'>): string {
  return d.line.toUpperCase() + '|' + (d.terminus ?? d.destination);
}

/** Per line + direction only the rows of the stop with the shortest walk; tied stops all stay. */
export function nearestOnly(rows: readonly MergedRow[], stops: readonly StopView[]): MergedRow[] {
  const walk = new Map(stops.map((s) => [s.entityId, s.walkMin]));
  const walkOf = (row: MergedRow): number => walk.get(row.entityId) ?? 0;
  const best = new Map<string, number>();
  for (const row of rows) {
    const key = directionKey(row.departure);
    const current = best.get(key);
    if (current === undefined || walkOf(row) < current) best.set(key, walkOf(row));
  }
  return rows.filter((row) => walkOf(row) === best.get(directionKey(row.departure)));
}

/** Visible departures of all stops (each with its own walk time) in one list, by time then line, at most `rows`. */
export function mergeDepartures(
  stops: readonly StopView[],
  now: number,
  rows: number,
  hideMissed: boolean,
  nearest = false,
): MergedRow[] {
  const all: MergedRow[] = stops.flatMap((stop) =>
    visibleDepartures(stop.departures, now, Number.POSITIVE_INFINITY, stop.walkMin, hideMissed).map((row) => ({
      ...row,
      entityId: stop.entityId,
      stopName: stop.name,
    })),
  );
  // Before the rows limit, so the list still fills up to `rows`.
  const merged = nearest ? nearestOnly(all, stops) : all;
  merged.sort(
    (a, b) =>
      Date.parse(a.departure.departs_at) - Date.parse(b.departure.departs_at) ||
      a.departure.line.localeCompare(b.departure.line, undefined, { numeric: true }),
  );
  return merged.slice(0, rows);
}

/** Night lines (N…) dark, then tram / trolleybus / bus; unknown mode neutral grey. */
export function badgeColor(mode: string | null, line: string): string {
  if (line.toUpperCase().startsWith('N')) return BADGE_COLORS.night;
  if (mode === 'tram') return BADGE_COLORS.tram;
  if (mode === 'trolleybus') return BADGE_COLORS.trolleybus;
  if (mode === 'bus') return BADGE_COLORS.bus;
  return BADGE_COLORS.neutral;
}

/** Badge colors: iMHD's own line colors when known, else the mode color on white text. */
export function badgeStyle(d: Pick<Departure, 'mode' | 'line' | 'color' | 'text_color'>): {
  background: string;
  color: string;
} {
  return { background: d.color ?? badgeColor(d.mode, d.line), color: d.text_color ?? '#fff' };
}

/** "nást. A" from the iMHD platform letter; null without a letter (the internal id is never shown). */
export function platformText(d: Pick<Departure, 'platform_label'>, t: Strings): string | null {
  return d.platform_label ? t.platform(d.platform_label) : null;
}

/** "4 min pešo" for a stop with a walk time; null at 0. */
export function walkText(walkMin: number, t: Strings): string | null {
  return walkMin > 0 ? t.walk(walkMin) : null;
}

/** The status text of a stop header; null while live (the green dot says it). */
export function headerText(
  status: Status,
  lastLive: string | null,
  t: Strings,
  formatTime: (iso: string) => string,
): string | null {
  if (status === 'live') return null;
  if (lastLive) return t.lastLive(formatTime(lastLive));
  return status === 'connecting' ? t.connecting : t.unavailable;
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null;

function readDeparture(raw: unknown): Departure | null {
  if (!isRecord(raw)) return null;
  const { line, mode, destination, departs_at, scheduled_at, realtime, delay_min, platform } = raw;
  const { platform_label, color, text_color, terminus } = raw;
  const text = (value: unknown): string | null => (typeof value === 'string' && value.trim() !== '' ? value : null);
  if (typeof line !== 'string' || typeof destination !== 'string' || typeof departs_at !== 'string') return null;
  return {
    line,
    mode: typeof mode === 'string' ? mode : null,
    destination,
    terminus: text(terminus),
    departs_at,
    scheduled_at: typeof scheduled_at === 'string' ? scheduled_at : departs_at,
    realtime: realtime === true,
    delay_min: typeof delay_min === 'number' ? delay_min : 0,
    platform: typeof platform === 'number' && Number.isFinite(platform) ? platform : null,
    platform_label: text(platform_label),
    color: text(color),
    text_color: text(text_color),
  };
}

function readStatus(value: unknown): Status {
  return value === 'live' || value === 'connecting' ? value : 'unavailable';
}

/** The friendly name without the entity suffix ("Zochova Odchody" -> "Zochova"). */
export function stopName(friendlyName: unknown, entityId: string): string {
  if (typeof friendlyName !== 'string' || friendlyName.trim() === '') return entityId;
  return friendlyName.replace(/\s+(Odchody|Departures)$/u, '').trim() || friendlyName;
}

/** Reads one stop sensor into what the card draws; name: config, then `stop_name`, then the friendly name. */
export function readStop(entity: HassEntity, name?: string): StopView {
  const a = entity.attributes;
  const departures = Array.isArray(a['departures']) ? a['departures'].map(readDeparture) : [];
  return {
    entityId: entity.entity_id,
    name:
      name ??
      (typeof a['stop_name'] === 'string' && a['stop_name'].trim() !== ''
        ? a['stop_name']
        : stopName(a['friendly_name'], entity.entity_id)),
    status: readStatus(a['status']),
    lastLive: typeof a['last_live'] === 'string' ? a['last_live'] : null,
    walkMin: typeof a['walk_min'] === 'number' ? a['walk_min'] : 0,
    departures: departures.filter((d): d is Departure => d !== null),
  };
}
