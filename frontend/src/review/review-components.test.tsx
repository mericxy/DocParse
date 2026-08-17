import { useState } from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import type { CardValue, PayrollValue } from "../types/transcription";
import { PdfViewer } from "../components/PdfViewer";
import { CardReview } from "./CardReview";
import { PayrollReview } from "./PayrollReview";

it("keeps a day without punches visible and preserves raw while safely normalizing time", async () => {
  const value: CardValue = {
    pages: [
      {
        page: 1,
        days: [
          { date_raw: "01/01/2025", punches: [] },
          {
            date_raw: "02/01/2025",
            punches: [{ kind: "IN", time_raw: "+08:00d", time_hhmm: "08:00" }],
          },
        ],
      },
    ],
  };
  const onChange = vi.fn();
  render(<CardReview value={value} onChange={onChange} />);

  expect(screen.getByLabelText("Data da página 1, linha 1")).toHaveValue("01/01/2025");
  for (const addButton of screen.getAllByRole("button", { name: "+ adicionar" })) {
    expect(addButton).toHaveClass("cell-input", "time-input", "empty-time-input");
  }
  const input = screen.getByLabelText("Entrada 1 de 02/01/2025");
  fireEvent.change(input, { target: { value: "8:25" } });

  const lastValue = onChange.mock.calls.at(-1)?.[0] as CardValue;
  expect(lastValue.pages[0].days[1].punches[0]).toEqual({
    kind: "IN",
    time_raw: "8:25",
    time_hhmm: "08:25",
  });
});

it("renders repeated payroll labels as separate editors and updates only the selected field", async () => {
  const value: PayrollValue = {
    pages: [
      {
        page: 2,
        year: "2025",
        month: "12",
        fields: [
          { code: "100", label: "13º Normal", reference: "", value: "100,00" },
          { code: "101", label: "13º Normal", reference: "", value: "200,00" },
        ],
        bases: [{ label: "Base INSS", value: "300,00" }],
      },
    ],
  };
  const onChange = vi.fn();
  render(<PayrollReview value={value} onChange={onChange} />);

  expect(screen.getByText("2 registros")).toBeInTheDocument();
  const second = screen.getByLabelText("Valor da verba 2, linha 1");
  fireEvent.change(second, { target: { value: "2.3?9,77" } });

  const lastValue = onChange.mock.calls.at(-1)?.[0] as PayrollValue;
  expect(lastValue.pages[0].fields[0].value).toBe("100,00");
  expect(lastValue.pages[0].fields[1].value).toBe("2.3?9,77");
  expect(lastValue.pages[0].bases).toEqual([{ label: "Base INSS", value: "300,00" }]);
});

it("edits code, label, reference and value of one field by its array index", () => {
  const initial: PayrollValue = {
    pages: [{
      page: 1,
      year: "2025",
      month: "01",
      fields: [{ code: "001", label: "SALARIO", reference: "220,00", value: "1.000,00" }],
      bases: [],
    }],
  };
  let latest = initial;
  function Harness() {
    const [value, setValue] = useState(initial);
    return <PayrollReview value={value} onChange={(next) => { latest = next; setValue(next); }} />;
  }
  render(<Harness />);

  fireEvent.change(screen.getByLabelText("Código da verba 1, linha 1"), { target: { value: "009" } });
  fireEvent.change(screen.getByLabelText("Label da verba 1, linha 1"), { target: { value: "SALÁRIO CORRIGIDO" } });
  fireEvent.change(screen.getByLabelText("Referência da verba 1, linha 1"), { target: { value: "200,00" } });
  fireEvent.change(screen.getByLabelText("Valor da verba 1, linha 1"), { target: { value: "9.999,99" } });

  expect(latest.pages[0].fields[0]).toEqual({
    code: "009",
    label: "SALÁRIO CORRIGIDO",
    reference: "200,00",
    value: "9.999,99",
  });
});

it("represents every empty card page and explains a completely empty transcription", () => {
  const value: CardValue = {
    pages: [{ page: 1, days: [] }, { page: 2, days: [] }],
  };
  render(<CardReview value={value} onChange={vi.fn()} />);

  expect(screen.getByText("Página 1 — nenhum dia extraído")).toBeInTheDocument();
  expect(screen.getByText("Página 2 — nenhum dia extraído")).toBeInTheDocument();
  expect(screen.getAllByText("Página sem dias extraídos")).toHaveLength(2);
});

it("keeps the native PDF viewer and offers a lightweight new-tab fallback", () => {
  render(<PdfViewer url="blob:docparse-pdf" filename="documento.pdf" />);

  expect(screen.getByTitle("Visualização de documento.pdf")).toHaveAttribute(
    "src",
    "blob:docparse-pdf",
  );
  expect(screen.getByRole("link", { name: "Abrir em nova guia" })).toHaveAttribute(
    "href",
    "blob:docparse-pdf",
  );
});

it("uses a compact accessible indicator for all payroll warning reasons", () => {
  const value: PayrollValue = {
    pages: [
      {
        page: 1,
        year: "2025",
        month: "01",
        fields: [{ code: "001", label: "SALARIO", reference: "", value: "1.000,00" }],
        bases: [],
      },
      {
        page: 2,
        year: "2025",
        month: "03",
        fields: [{ code: "002", label: "DESCONTO", reference: "", value: "1?0,00" }],
        bases: [],
      },
    ],
  };
  render(<PayrollReview value={value} onChange={vi.fn()} />);

  const indicator = screen.getByLabelText(
    "Advertências: Contém caracteres incertos (?); Mês não sequencial",
  );
  expect(indicator).toHaveClass("warning-indicator");
  expect(indicator).toHaveAttribute("tabindex", "0");
  expect(indicator).toHaveTextContent("⚠");
  const tooltip = within(indicator).getByRole("tooltip");
  expect(tooltip).toHaveTextContent("Contém caracteres incertos (?)");
  expect(tooltip).toHaveTextContent("Mês não sequencial");
});

it("keeps bases in an independent subtable and updates the selected base", async () => {
  const initial: PayrollValue = {
    pages: [{
      page: 2,
      year: "2017",
      month: "12",
      fields: Array.from({ length: 12 }, (_, index) => ({
        code: String(index + 1),
        label: `Verba ${index + 1}`,
        reference: "",
        value: `${index + 1},00`,
      })),
      bases: [
        { label: "Base INSS", value: "2.545,68" },
        { label: "Valor Líquido", value: "2.282,81" },
      ],
    }],
  };
  let latest = initial;
  function Harness() {
    const [value, setValue] = useState(initial);
    return <PayrollReview value={value} onChange={(next) => { latest = next; setValue(next); }} />;
  }
  const user = userEvent.setup();
  render(<Harness />);

  const fieldsTable = screen.getByRole("table", { name: "Verbas do holerite" });
  const headerCount = fieldsTable.querySelectorAll(":scope > thead > tr > th").length;
  await user.click(screen.getByText("Bases e totais"));

  const basesTable = screen.getByRole("table", { name: "Bases e totais da linha 1" });
  expect(basesTable).toHaveClass("bases-subtable");
  expect(basesTable).not.toBe(fieldsTable);
  expect(fieldsTable.querySelectorAll(":scope > thead > tr > th")).toHaveLength(headerCount);

  fireEvent.change(screen.getByLabelText("Valor da base 2, linha 1"), {
    target: { value: "9.999,99" },
  });
  expect(latest.pages[0].bases).toEqual([
    { label: "Base INSS", value: "2.545,68" },
    { label: "Valor Líquido", value: "9.999,99" },
  ]);
});
