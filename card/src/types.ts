/** The parts of Home Assistant the card reads. */
export interface HassEntity {
  entity_id: string;
  state: string;
  attributes: Record<string, unknown>;
}

export interface HomeAssistant {
  states: Record<string, HassEntity | undefined>;
  locale?: { language: string; time_zone?: string };
  language?: string;
  config?: { time_zone?: string };
}

export type Status = 'live' | 'connecting' | 'unavailable';

/** One departure of the sensor attribute `departures`. */
export interface Departure {
  line: string;
  mode: string | null;
  destination: string;
  /** The trip's terminus (same at every stop, unlike `destination`); null = unknown, use the destination. */
  terminus: string | null;
  departs_at: string;
  scheduled_at: string;
  realtime: boolean;
  delay_min: number;
  /** The board platform (`nastupiste`) the departure leaves from; null when unknown. */
  platform: number | null;
  /** The platform as iMHD shows it at the stop ("A"); null when unknown. */
  platform_label: string | null;
  /** iMHD line colors (CSS values); null = use the mode color / white. */
  color: string | null;
  text_color: string | null;
}

/** What the card needs from one stop sensor. */
export interface StopView {
  entityId: string;
  name: string;
  status: Status;
  lastLive: string | null;
  walkMin: number;
  departures: Departure[];
}

export interface EntityConfig {
  entity: string;
  name?: string;
  rows?: number;
}

export type Layout = 'merged' | 'stack' | 'columns';

/** line: iMHD / mode colors; neutral: theme colors (`--imhd-badge-background`, `--imhd-badge-color`). */
export type BadgeKind = 'line' | 'neutral';

export interface CardConfig {
  type: string;
  title?: string;
  /** Short text on the right of the title (merged layout). */
  subtitle?: string;
  /** merged: total rows; stack/columns: per stop. */
  rows: number;
  layout: Layout;
  /** From this many minutes on the time shows as HH:MM. */
  clock_after: number;
  language?: 'sk' | 'en';
  hide_missed: boolean;
  /** merged: a line + direction leaving from several stops shows only from the stop with the shortest walk. */
  nearest_only: boolean;
  /** merged: "4 min pešo" on the second line when the stop has a walk time. */
  show_walk: boolean;
  badge: BadgeKind;
  entities: EntityConfig[];
}

/** A departure ready to draw. */
export interface VisibleRow {
  departure: Departure;
  minutes: number;
  missed: boolean;
}

/** A row of the merged list: a visible departure plus the stop it leaves from. */
export interface MergedRow extends VisibleRow {
  entityId: string;
  stopName: string;
}

/** What the time column shows. */
export type TimeLabel = { kind: 'now' } | { kind: 'minutes'; value: number } | { kind: 'clock'; value: string };
