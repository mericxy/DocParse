function hasPossibleValue(component: string, maximum: number): boolean {
  const values = [""];
  for (const character of component) {
    const digits = character === "?" ? "0123456789" : character;
    const current = values.splice(0, values.length);
    for (const prefix of current) {
      for (const digit of digits) values.push(`${prefix}${digit}`);
    }
  }
  return values.some((value) => Number(value) <= maximum);
}

/** Mirror the backend's conservative, evidence-backed time normalization. */
export function normalizeEditedTime(raw: string): string {
  const compact = raw.replace(/\s+/g, "");
  const match = /^\+?([0-9?]{1,2})[:hH.]([0-9?]{2})([A-Za-z]?)$/.exec(compact);
  if (!match) return raw;

  let [, hour, minute, suffix] = match;
  if (suffix && !["c", "d"].includes(suffix.toLowerCase())) return raw;
  if (hour.includes("?") || minute.includes("?")) return `${hour}:${minute}`;
  if (hour.length === 1) hour = `0${hour}`;
  if (!hasPossibleValue(hour, 23)) hour = "?".repeat(hour.length);
  if (!hasPossibleValue(minute, 59)) minute = "??";
  return `${hour}:${minute}`;
}
