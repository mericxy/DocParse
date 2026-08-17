import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import App from "../App";
import type { CardValue, PayrollValue } from "../types/transcription";
import { WarningReasons } from "./WarningReasons";
import { ReviewWorkspace } from "./ReviewWorkspace";

const cardValue: CardValue = {
  pages: [{ page: 1, days: [{ date_raw: "01", punches: [] }] }],
};

function renderWorkspace() {
  return render(
    <ReviewWorkspace
      type="cartao-ponto"
      value={cardValue}
      pdfUrl="blob:docparse-pdf"
      filename="cartao.pdf"
      dirty={false}
      saving={false}
      downloading={null}
      feedback={null}
      onChange={vi.fn()}
      onSave={vi.fn()}
      onDownload={vi.fn()}
    />,
  );
}

it("switches between split, data-only and PDF-only workspace states", async () => {
  const user = userEvent.setup();
  const { container } = renderWorkspace();
  const workspace = container.querySelector(".review-workspace");

  expect(workspace).toHaveClass("panels-both");
  expect(screen.getByRole("heading", { name: "PDF original" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Dados do cartão" })).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Ocultar PDF" }));
  expect(workspace).toHaveClass("panels-data");
  expect(screen.queryByRole("heading", { name: "PDF original" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Mostrar PDF" }));

  expect(workspace).toHaveClass("panels-both");
  await user.click(screen.getByRole("button", { name: "Ocultar dados" }));
  expect(workspace).toHaveClass("panels-pdf");
  expect(screen.queryByRole("heading", { name: "Dados do cartão" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Mostrar dados" }));
  expect(workspace).toHaveClass("panels-both");
});

it("exposes compact warning reasons on keyboard focus", async () => {
  const user = userEvent.setup();
  render(
    <WarningReasons
      compact
      warning={{
        severity: "red",
        reasons: ["Contém caracteres incertos (?)", "Mês não sequencial"],
      }}
    />,
  );

  const indicator = screen.getByLabelText(
    "Advertências: Contém caracteres incertos (?); Mês não sequencial",
  );
  await user.tab();
  expect(indicator).toHaveFocus();
  expect(screen.getByRole("tooltip")).toHaveTextContent("Contém caracteres incertos (?)");
  expect(screen.getByRole("tooltip")).toHaveTextContent("Mês não sequencial");
});

it("places document warnings as an icon beside the data panel actions", () => {
  const payrollValue: PayrollValue = {
    pages: [
      {
        page: 1,
        year: "2025",
        month: "01",
        fields: [
          { code: "1", label: "SALARIO", reference: "", value: "100,00" },
          { code: "2", label: "SALARIO", reference: "", value: "2?0,00" },
        ],
        bases: [],
      },
    ],
  };
  render(
    <ReviewWorkspace
      type="holerite"
      value={payrollValue}
      pdfUrl="blob:docparse-pdf"
      filename="holerite.pdf"
      dirty={false}
      saving={false}
      downloading={null}
      feedback={null}
      onChange={vi.fn()}
      onSave={vi.fn()}
      onDownload={vi.fn()}
    />,
  );

  expect(screen.queryByText("Verbas repetidas")).not.toBeInTheDocument();
  const warning = screen.getByLabelText(/Verbas repetidas detectadas/);
  expect(warning.closest(".panel-actions")).toBeInTheDocument();
  expect(warning).toHaveTextContent("⚠");
  expect(screen.getByRole("button", { name: "Ocultar dados" })).toBeInTheDocument();
  const tooltip = within(warning).getByRole("tooltip");
  expect(tooltip).toHaveTextContent(
    'CSV e XLSX usarão colunas adicionais, como "INSS (2)"',
  );
  expect(tooltip).toHaveTextContent("Contém caracteres incertos (?)");
  expect(screen.getByRole("button", { name: "Baixar XLSX" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Baixar CSV" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Baixar JSON" })).toBeEnabled();
});

it("uses the compact header and the product footer", () => {
  const { container } = render(<App />);

  expect(container.querySelector(".brand-mark")).not.toBeInTheDocument();
  expect(screen.getByText("Processamento local")).toBeInTheDocument();
  expect(screen.getByText("DocParse © 2026")).toBeInTheDocument();
  const repository = screen.getByRole("link", { name: "Repositório" });
  expect(repository).toHaveAttribute("href", "https://github.com/mericxy/DocParse");
  expect(repository).toHaveAttribute("target", "_blank");
  expect(repository).toHaveAttribute("rel", "noopener noreferrer");
});
