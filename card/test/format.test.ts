import { describe, expect, it } from 'vitest';
import {
  BADGE_COLORS,
  badgeColor,
  badgeStyle,
  headerText,
  mergeDepartures,
  minutesUntil,
  nearestOnly,
  platformText,
  readStop,
  stopName,
  timeLabel,
  visibleDepartures,
  walkText,
} from '../src/format';
import { strings } from '../src/i18n';
import type { Departure, StopView } from '../src/types';

const NOW = Date.parse('2026-11-05T04:42:00.000Z');
const at = (offsetMs: number): string => new Date(NOW + offsetMs).toISOString();
const dep = (offsetMs: number, patch: Partial<Departure> = {}): Departure => ({
  line: '30',
  mode: 'bus',
  destination: 'Centrum',
  terminus: null,
  departs_at: at(offsetMs),
  scheduled_at: at(offsetMs),
  realtime: true,
  delay_min: 0,
  platform: null,
  platform_label: null,
  color: null,
  text_color: null,
  ...patch,
});

describe('minutesUntil', () => {
  it('rounds up to whole minutes and never goes below 0', () => {
    expect(minutesUntil(at(1), NOW)).toBe(1);
    expect(minutesUntil(at(60_000), NOW)).toBe(1);
    expect(minutesUntil(at(60_001), NOW)).toBe(2);
    expect(minutesUntil(at(0), NOW)).toBe(0);
    expect(minutesUntil(at(-20_000), NOW)).toBe(0);
  });
});

describe('visibleDepartures', () => {
  const departures = [dep(-40_000), dep(-10_000), dep(120_000), dep(240_000), dep(600_000)];

  it('drops departed vehicles (older than 30 s) and keeps at most `rows`', () => {
    expect(visibleDepartures(departures, NOW, 3, 0, false).map((r) => r.minutes)).toEqual([0, 2, 4]);
    expect(visibleDepartures(departures, NOW, 10, 0, false)).toHaveLength(4);
  });

  it('marks rows you cannot catch, or hides them', () => {
    expect(visibleDepartures(departures, NOW, 3, 4, false).map((r) => [r.minutes, r.missed])).toEqual([
      [0, true],
      [2, true],
      [4, false],
    ]);
    expect(visibleDepartures(departures, NOW, 3, 4, true).map((r) => r.minutes)).toEqual([4, 10]);
  });
});

describe('badgeColor', () => {
  it('colors by mode, night lines dark, unknown grey', () => {
    expect(badgeColor('tram', '4')).toBe(BADGE_COLORS.tram);
    expect(badgeColor('trolleybus', '47')).toBe(BADGE_COLORS.trolleybus);
    expect(badgeColor('bus', '30')).toBe(BADGE_COLORS.bus);
    expect(badgeColor('bus', 'N33')).toBe(BADGE_COLORS.night);
    expect(badgeColor(null, 'n1')).toBe(BADGE_COLORS.night);
    expect(badgeColor(null, '12')).toBe(BADGE_COLORS.neutral);
  });
});

describe('headerText', () => {
  const sk = strings('sk');
  const en = strings('en-GB');
  const hhmm = (iso: string): string => iso.slice(11, 16);

  it('is empty while live and explains every other state', () => {
    expect(headerText('live', at(0), sk, hhmm)).toBeNull();
    expect(headerText('connecting', '2026-11-05T21:12:00.000Z', sk, hhmm)).toBe('Naposledy online 21:12');
    expect(headerText('unavailable', '2026-11-05T21:12:00.000Z', en, hhmm)).toBe('Last online 21:12');
    expect(headerText('connecting', null, sk, hhmm)).toBe('Pripája sa…');
    expect(headerText('unavailable', null, sk, hhmm)).toBe('Nedostupné');
    expect(headerText('unavailable', null, en, hhmm)).toBe('Unavailable');
  });
});

describe('readStop', () => {
  it('reads the sensor attributes defensively', () => {
    const stop = readStop({
      entity_id: 'sensor.imhd_zochova',
      state: at(120_000),
      attributes: {
        friendly_name: 'Zochova Odchody',
        status: 'live',
        walk_min: 4,
        last_live: at(0),
        departures: [dep(120_000), { line: 5 }, null],
      },
    });
    expect(stop).toMatchObject({ name: 'Zochova', status: 'live', walkMin: 4, lastLive: at(0) });
    expect(stop.departures).toHaveLength(1);
    expect(readStop({ entity_id: 'sensor.x', state: 'unknown', attributes: {} }, 'Domov')).toMatchObject({
      name: 'Domov',
      status: 'unavailable',
      walkMin: 0,
      departures: [],
    });
    expect(stopName('Hodžovo nám. Departures', 'sensor.y')).toBe('Hodžovo nám.');
    expect(stopName(undefined, 'sensor.y')).toBe('sensor.y');
  });
});

describe('timeLabel', () => {
  const zone = 'Europe/Bratislava';

  it('shows now, minutes below clock_after and the clock time from it on', () => {
    expect(timeLabel(at(0), NOW, 60, zone)).toEqual({ kind: 'now' });
    expect(timeLabel(at(59 * 60_000), NOW, 60, zone)).toEqual({ kind: 'minutes', value: 59 });
    // 04:42Z + 60 min = 05:42Z = 06:42 in Bratislava (CET).
    expect(timeLabel(at(60 * 60_000), NOW, 60, zone)).toEqual({ kind: 'clock', value: '06:42' });
    expect(timeLabel(at(10 * 60_000), NOW, 5, zone)).toEqual({ kind: 'clock', value: '05:52' });
  });

  it('formats the clock in the Home Assistant time zone across midnight', () => {
    const late = Date.parse('2026-11-05T22:30:00.000Z'); // 23:30 in Bratislava
    expect(timeLabel('2026-11-05T23:47:00.000Z', late, 60, zone)).toEqual({ kind: 'clock', value: '00:47' });
    expect(timeLabel('2026-11-05T23:47:00.000Z', late, 60, 'UTC')).toEqual({ kind: 'clock', value: '23:47' });
  });
});

describe('mergeDepartures', () => {
  const stop = (entityId: string, name: string, walkMin: number, departures: Departure[]): StopView => ({
    entityId,
    name,
    status: 'live',
    lastLive: at(0),
    walkMin,
    departures,
  });
  const a = stop('sensor.imhd_a', 'Zochova', 0, [
    dep(-40_000, { line: '20' }),
    dep(120_000, { line: '20', platform: 1311 }),
    dep(600_000, { line: '21', platform: 1310 }),
  ]);
  const b = stop('sensor.imhd_b', 'Hodžovo nám.', 3, [
    dep(60_000, { line: '93' }),
    dep(120_000, { line: '9', platform: 2 }),
    dep(300_000, { line: '31' }),
  ]);

  it('sorts across stops by time then line, keeps at most rows, drops departed', () => {
    const rows = mergeDepartures([a, b], NOW, 10, false);
    expect(rows.map((r) => [r.departure.line, r.minutes])).toEqual([
      ['93', 1],
      ['9', 2],
      ['20', 2],
      ['31', 5],
      ['21', 10],
    ]);
    expect(mergeDepartures([a, b], NOW, 2, false).map((r) => r.departure.line)).toEqual(['93', '9']);
  });

  it('applies each stop walk time and keeps the stop on every row', () => {
    const rows = mergeDepartures([a, b], NOW, 10, false);
    expect(rows.filter((r) => r.missed).map((r) => r.departure.line)).toEqual(['93', '9']);
    expect(rows[1]).toMatchObject({ entityId: 'sensor.imhd_b', stopName: 'Hodžovo nám.' });
    expect(rows[2]).toMatchObject({ entityId: 'sensor.imhd_a', stopName: 'Zochova' });
    expect(rows[2]?.departure.platform).toBe(1311);
    expect(mergeDepartures([a, b], NOW, 10, true).map((r) => r.departure.line)).toEqual(['20', '31', '21']);
  });
});

describe('readStop stop_name and platform', () => {
  it('prefers stop_name over the friendly name and parses the platform', () => {
    const stop = readStop({
      entity_id: 'sensor.imhd_zochova',
      state: at(120_000),
      attributes: {
        friendly_name: 'Zochova Odchody',
        stop_name: 'Nám. 1. mája',
        status: 'live',
        departures: [dep(60_000, { platform: 1311 }), dep(120_000), { ...dep(180_000), platform: '7' }],
      },
    });
    expect(stop.name).toBe('Nám. 1. mája');
    expect(stop.departures.map((d) => d.platform)).toEqual([1311, null, null]);
    const legacy = { ...dep(60_000), platform: undefined };
    const old = readStop({ entity_id: 'sensor.x', state: 'x', attributes: { departures: [legacy] } }, 'Domov');
    expect(old.name).toBe('Domov');
    expect(old.departures[0]?.platform).toBeNull();
  });
});

describe('badgeStyle', () => {
  it('uses the iMHD line colors when provided, else the mode color on white', () => {
    expect(badgeStyle(dep(0, { line: '21', color: 'rgb(51,134,50)', text_color: 'rgb(255,255,255)' }))).toEqual({
      background: 'rgb(51,134,50)',
      color: 'rgb(255,255,255)',
    });
    expect(badgeStyle(dep(0, { line: 'N21', color: 'rgb(43,42,41)' }))).toEqual({
      background: 'rgb(43,42,41)',
      color: '#fff',
    });
    expect(badgeStyle(dep(0, { line: '4', mode: 'tram' }))).toEqual({ background: BADGE_COLORS.tram, color: '#fff' });
  });
});

describe('platformText', () => {
  it('shows the iMHD platform letter and never the raw id', () => {
    expect(platformText(dep(0, { platform: 1310, platform_label: 'A' }), strings('sk'))).toBe('nást. A');
    expect(platformText(dep(0, { platform: 1310, platform_label: 'A' }), strings('en'))).toBe('platform A');
    expect(platformText(dep(0, { platform: 1310 }), strings('sk'))).toBeNull();
  });

  it('reads the label and colors from the sensor defensively', () => {
    const stop = readStop({
      entity_id: 'sensor.x',
      state: 'x',
      attributes: {
        departures: [
          { ...dep(60_000), platform: 1311, platform_label: 'B', color: '#0064b4', text_color: '#fff' },
          { ...dep(120_000), platform_label: 7, color: '', text_color: undefined },
        ],
      },
    });
    expect(stop.departures.map((d) => [d.platform_label, d.color, d.text_color])).toEqual([
      ['B', '#0064b4', '#fff'],
      [null, null, null],
    ]);
  });
});

describe('nearestOnly', () => {
  const stop = (entityId: string, name: string, walkMin: number, departures: Departure[]): StopView => ({
    entityId,
    name,
    status: 'live',
    lastLive: at(0),
    walkMin,
    departures,
  });
  const toStation = { line: 'N21', destination: 'Hlavná stanica', terminus: 'Hlavná stanica' };
  const near = stop('sensor.imhd_kamenne_nam', 'Kamenné nám.', 3, [
    dep(600_000, { ...toStation, destination: 'Hlavná stanica ► Centrum' }),
    dep(900_000, { line: '30' }),
  ]);
  const far = stop('sensor.imhd_zochova', 'Nám. 1. mája', 6, [
    dep(240_000, { ...toStation, line: 'n21' }),
    dep(480_000, toStation),
    dep(540_000, { line: 'N21', destination: 'Patrónka', terminus: 'Patrónka' }),
    dep(720_000, { line: '31' }),
  ]);
  const show = (rows: { departure: Departure; stopName: string }[]): string[][] =>
    rows.map((r) => [r.departure.line, r.departure.terminus ?? r.departure.destination, r.stopName]);

  it('shows N21 to Hlavná stanica only from the closer stop, the other direction stays', () => {
    expect(show(mergeDepartures([near, far], NOW, 10, false, true))).toEqual([
      ['N21', 'Patrónka', 'Nám. 1. mája'],
      ['N21', 'Hlavná stanica', 'Kamenné nám.'],
      ['31', 'Centrum', 'Nám. 1. mája'],
      ['30', 'Centrum', 'Kamenné nám.'],
    ]);
    // Off: every stop keeps its rows.
    expect(mergeDepartures([near, far], NOW, 10, false)).toHaveLength(6);
  });

  it('keeps every stop when the walk times are equal', () => {
    for (const walk of [0, 4]) {
      const a = { ...near, walkMin: walk };
      const b = { ...far, walkMin: walk };
      expect(mergeDepartures([a, b], NOW, 10, false, true)).toHaveLength(6);
    }
    const tied = [near, { ...far, walkMin: 3 }];
    expect(nearestOnly(mergeDepartures(tied, NOW, 10, false), tied)).toHaveLength(6);
  });

  it('dedupes before the rows limit so the list still fills', () => {
    expect(show(mergeDepartures([near, far], NOW, 2, false))).toEqual([
      ['n21', 'Hlavná stanica', 'Nám. 1. mája'],
      ['N21', 'Hlavná stanica', 'Nám. 1. mája'],
    ]);
    expect(show(mergeDepartures([near, far], NOW, 2, false, true))).toEqual([
      ['N21', 'Patrónka', 'Nám. 1. mája'],
      ['N21', 'Hlavná stanica', 'Kamenné nám.'],
    ]);
  });

  it('falls back to the destination without a terminus', () => {
    const a = stop('sensor.a', 'A', 1, [dep(60_000, { line: '30' })]);
    const b = stop('sensor.b', 'B', 5, [dep(120_000, { line: '30' }), dep(180_000, { line: '30', destination: 'Kuchajda' })]);
    expect(show(mergeDepartures([a, b], NOW, 10, false, true))).toEqual([
      ['30', 'Centrum', 'A'],
      ['30', 'Kuchajda', 'B'],
    ]);
  });
});

describe('walkText', () => {
  it('shows the walk time of a stop, nothing at 0', () => {
    expect(walkText(4, strings('sk'))).toBe('4 min pešo');
    expect(walkText(4, strings('en'))).toBe('4 min walk');
    expect(walkText(0, strings('sk'))).toBeNull();
  });

  it('reads the terminus from the sensor', () => {
    const stop = readStop({
      entity_id: 'sensor.x',
      state: 'x',
      attributes: { departures: [{ ...dep(60_000), terminus: 'Hlavná stanica' }, { ...dep(120_000), terminus: '' }] },
    });
    expect(stop.departures.map((d) => d.terminus)).toEqual(['Hlavná stanica', null]);
  });
});
