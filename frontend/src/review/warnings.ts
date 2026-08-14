import type {
  CardValue,
  Day,
  PayrollPage,
  PayrollValue,
} from "../types/transcription";

export type WarningSeverity = "none" | "yellow" | "red";

export interface RowWarning {
  severity: WarningSeverity;
  reasons: string[];
}

export interface CardReviewRow {
  pageIndex: number;
  dayIndex: number;
  page: number;
  day: Day;
  warning: RowWarning;
}

export interface PayrollReviewRow {
  pageIndex: number;
  page: PayrollPage;
  warning: RowWarning;
}

function containsQuestion(value: unknown): boolean {
  if (typeof value === "string") return value.includes("?");
  if (Array.isArray(value)) return value.some(containsQuestion);
  if (value && typeof value === "object") {
    return Object.values(value).some(containsQuestion);
  }
  return false;
}

function parseDate(raw: string): number | null {
  const match = /^(\d{1,2})([/.-])(\d{1,2})\2(\d{2}|\d{4})$/.exec(raw);
  if (!match) return null;
  const day = Number(match[1]);
  const month = Number(match[3]);
  const year = match[4].length === 2 ? 2000 + Number(match[4]) : Number(match[4]);
  const utc = Date.UTC(year, month - 1, day);
  const date = new Date(utc);
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    return null;
  }
  return utc;
}

function parseDayOnly(raw: string): number | null {
  if (!/^\d{1,2}$/.test(raw)) return null;
  const day = Number(raw);
  return day >= 1 && day <= 31 ? day : null;
}

function parseCompetence(page: PayrollPage): [number, number] | null {
  if (
    page.year.includes("?") ||
    page.month.includes("?") ||
    !/^\d{4}$/.test(page.year) ||
    !/^\d{1,2}$/.test(page.month)
  ) {
    return null;
  }
  const month = Number(page.month);
  if (month < 1 || month > 12) return null;
  return [Number(page.year), month];
}

function isNextMonth(previous: [number, number], current: [number, number]): boolean {
  const [year, month] = previous;
  return month === 12
    ? current[0] === year + 1 && current[1] === 1
    : current[0] === year && current[1] === month + 1;
}

export function maxPunchCount(value: CardValue): number {
  let maximum = 0;
  for (const page of value.pages) {
    for (const day of page.days) maximum = Math.max(maximum, day.punches.length);
  }
  // The matrix always exposes complete IN/OUT pairs, even when the document
  // currently has an odd final punch.
  return Math.ceil(maximum / 2) * 2;
}

export function cardReviewRows(value: CardValue): CardReviewRow[] {
  const rows: CardReviewRow[] = [];
  let previousDate: number | null = null;
  const oneDay = 24 * 60 * 60 * 1000;

  value.pages.forEach((page, pageIndex) => {
    // Without month/year, a day-only sequence is meaningful only inside the
    // physical page. Full dates keep their document-wide sequence.
    let previousDayOnly: number | null = null;
    page.days.forEach((day, dayIndex) => {
      const reasons: string[] = [];
      if (day.punches.length % 2 !== 0) reasons.push("Número ímpar de batidas");
      if (containsQuestion(day)) reasons.push("Contém caracteres incertos (?)");

      const currentDate = parseDate(day.date_raw);
      const currentDayOnly = parseDayOnly(day.date_raw);
      const nonSequentialFull =
        currentDate !== null &&
        previousDate !== null &&
        currentDate !== previousDate + oneDay;
      const nonSequentialDayOnly =
        currentDayOnly !== null &&
        previousDayOnly !== null &&
        currentDayOnly !== previousDayOnly + 1;
      const nonSequential = nonSequentialFull || nonSequentialDayOnly;
      if (nonSequential) reasons.push("Data não sequencial");

      rows.push({
        pageIndex,
        dayIndex,
        page: page.page,
        day,
        warning: {
          severity: nonSequential ? "red" : reasons.length ? "yellow" : "none",
          reasons,
        },
      });
      if (currentDate !== null) previousDate = currentDate;
      if (currentDayOnly !== null) previousDayOnly = currentDayOnly;
    });
  });
  return rows;
}

export function payrollFieldLabels(value: PayrollValue): string[] {
  const labels: string[] = [];
  const seen = new Set<string>();
  for (const page of value.pages) {
    for (const field of page.fields) {
      if (!seen.has(field.label)) {
        seen.add(field.label);
        labels.push(field.label);
      }
    }
  }
  return labels;
}

export function payrollReviewRows(value: PayrollValue): PayrollReviewRow[] {
  const rows: PayrollReviewRow[] = [];
  let previousCompetence: [number, number] | null = null;

  value.pages.forEach((page, pageIndex) => {
    const reasons: string[] = [];
    if (!page.fields.length && !page.bases.length) {
      reasons.push("Página sem dados extraídos");
    }
    if (containsQuestion(page)) reasons.push("Contém caracteres incertos (?)");

    const current = parseCompetence(page);
    const repeated =
      current !== null &&
      previousCompetence !== null &&
      current[0] === previousCompetence[0] &&
      current[1] === previousCompetence[1];
    const nonSequential =
      current !== null &&
      previousCompetence !== null &&
      !repeated &&
      !isNextMonth(previousCompetence, current);
    if (nonSequential) reasons.push("Mês não sequencial");

    rows.push({
      pageIndex,
      page,
      warning: {
        severity: nonSequential ? "red" : reasons.length ? "yellow" : "none",
        reasons,
      },
    });
    if (current !== null && !repeated) previousCompetence = current;
  });
  return rows;
}
