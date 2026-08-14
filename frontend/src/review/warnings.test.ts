import { describe, expect, it } from "vitest";

import type { CardValue, PayrollValue } from "../types/transcription";
import {
  cardReviewRows,
  maxPunchCount,
  payrollFieldLabels,
  payrollReviewRows,
} from "./warnings";

const punch = (kind: "IN" | "OUT", time: string) => ({
  kind,
  time_raw: time,
  time_hhmm: time,
});

describe("cartão de ponto", () => {
  it("preserves order, empty days and derives width from the largest punches array", () => {
    const value: CardValue = {
      pages: [
        {
          page: 2,
          days: [
            {
              date_raw: "02/01/2025",
              punches: [punch("IN", "08:00"), punch("OUT", "12:00"), punch("IN", "13:00")],
            },
            { date_raw: "01/01/2025", punches: [] },
          ],
        },
      ],
    };

    const rows = cardReviewRows(value);

    expect(maxPunchCount(value)).toBe(4);
    expect(rows.map((row) => row.day.date_raw)).toEqual(["02/01/2025", "01/01/2025"]);
    expect(rows[1].day.punches).toEqual([]);
    expect(rows[0].warning).toEqual({ severity: "yellow", reasons: ["Número ímpar de batidas"] });
    expect(rows[1].warning.severity).toBe("red");
  });

  it("red wins visually while retaining odd and uncertainty reasons", () => {
    const value: CardValue = {
      pages: [
        {
          page: 1,
          days: [
            { date_raw: "01/01/2025", punches: [] },
            { date_raw: "03/01/2025", punches: [punch("IN", "0?:00")] },
          ],
        },
      ],
    };

    expect(cardReviewRows(value)[1].warning).toEqual({
      severity: "red",
      reasons: [
        "Número ímpar de batidas",
        "Contém caracteres incertos (?)",
        "Data não sequencial",
      ],
    });
  });

  it("checks day-only dates inside a page without comparing page boundaries", () => {
    const value: CardValue = {
      pages: [
        { page: 1, days: [
          { date_raw: "01", punches: [] },
          { date_raw: "02", punches: [] },
          { date_raw: "03", punches: [] },
        ] },
        { page: 2, days: [
          { date_raw: "30", punches: [] },
          { date_raw: "31", punches: [] },
        ] },
        { page: 3, days: [{ date_raw: "01", punches: [] }] },
      ],
    };

    expect(cardReviewRows(value).map((row) => row.warning.severity)).toEqual([
      "none", "none", "none", "none", "none", "none",
    ]);
    value.pages[0].days[1].date_raw = "03";
    expect(cardReviewRows(value).slice(0, 3).map((row) => row.warning.severity)).toEqual([
      "none", "red", "red",
    ]);
  });
});

describe("holerite", () => {
  it("unions only field labels by first appearance and keeps equal page numbers as distinct rows", () => {
    const value: PayrollValue = {
      pages: [
        {
          page: 1,
          year: "2024",
          month: "12",
          fields: [
            { code: "2", label: "Verba B", reference: "", value: "2.389,77" },
            { code: "1", label: "Verba A", reference: "", value: "10,00" },
          ],
          bases: [{ label: "Base INSS", value: "2.399,77" }],
        },
        {
          page: 1,
          year: "2025",
          month: "01",
          fields: [{ code: "3", label: "Verba C", reference: "", value: "11,00" }],
          bases: [],
        },
      ],
    };

    expect(payrollFieldLabels(value)).toEqual(["Verba B", "Verba A", "Verba C"]);
    expect(payrollFieldLabels(value)).not.toContain("Base INSS");
    expect(payrollReviewRows(value)).toHaveLength(2);
    expect(payrollReviewRows(value).map((row) => row.page.page)).toEqual([1, 1]);
    expect(value.pages[0].fields[0].value).toBe("2.389,77");
  });

  it("handles empty, uncertain and non-sequential competences without false December rollover", () => {
    const value: PayrollValue = {
      pages: [
        { page: 1, year: "2024", month: "12", fields: [], bases: [{ label: "Total", value: "1,00" }] },
        { page: 2, year: "2025", month: "??", fields: [], bases: [] },
        { page: 3, year: "2025", month: "01", fields: [], bases: [{ label: "Total", value: "1,00" }] },
        { page: 4, year: "2025", month: "03", fields: [{ code: "", label: "A", reference: "", value: "1,?0" }], bases: [] },
      ],
    };

    const warnings = payrollReviewRows(value).map((row) => row.warning);
    expect(warnings[0].severity).toBe("none");
    expect(warnings[1].severity).toBe("yellow");
    expect(warnings[2].severity).toBe("none");
    expect(warnings[3].severity).toBe("red");
    expect(warnings[3].reasons).toContain("Contém caracteres incertos (?)");
    expect(warnings[3].reasons).toContain("Mês não sequencial");
  });

  it("ignores consecutive repeated competences before comparing the next distinct month", () => {
    const page = (month: string, year = "2024") => ({
      page: 1,
      year,
      month,
      fields: [{ code: "", label: month, reference: "", value: "1,00" }],
      bases: [],
    });
    const value: PayrollValue = {
      pages: [
        page("08"), page("08"), page("09"), page("09"), page("10"),
        page("12"), page("12"), page("01", "2025"),
      ],
    };

    expect(payrollReviewRows(value).map((row) => row.warning.severity)).toEqual([
      "none", "none", "none", "none", "none", "red", "none", "none",
    ]);
  });
});
