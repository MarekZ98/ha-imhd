/** Card texts in Slovak and English. */
export interface Strings {
  walk: (minutes: number) => string;
  lastLive: (time: string) => string;
  connecting: string;
  unavailable: string;
  now: string;
  min: string;
  noDepartures: string;
  timetable: string;
  delay: (minutes: number) => string;
  missingEntity: (entityId: string) => string;
  platform: (label: string) => string;
  stopStatus: (name: string, text: string) => string;
}

const SK: Strings = {
  walk: (m) => `${m} min pešo`,
  lastLive: (t) => `Naposledy online ${t}`,
  connecting: 'Pripája sa…',
  unavailable: 'Nedostupné',
  now: 'teraz',
  min: 'min',
  noDepartures: 'Žiadne odchody',
  timetable: 'podľa CP',
  delay: (m) => `+${m} min`,
  missingEntity: (id) => `Entita ${id} neexistuje`,
  platform: (label) => 'nást. ' + label,
  stopStatus: (name, text) => name + ': ' + text,
};

const EN: Strings = {
  walk: (m) => `${m} min walk`,
  lastLive: (t) => `Last online ${t}`,
  connecting: 'Connecting…',
  unavailable: 'Unavailable',
  now: 'now',
  min: 'min',
  noDepartures: 'No departures',
  timetable: 'timetable',
  delay: (m) => `+${m} min`,
  missingEntity: (id) => `Entity ${id} not found`,
  platform: (label) => 'platform ' + label,
  stopStatus: (name, text) => name + ': ' + text,
};

/** `sk` for Slovak, English otherwise. */
export function strings(language: string | undefined): Strings {
  return language?.toLowerCase().startsWith('sk') ? SK : EN;
}
