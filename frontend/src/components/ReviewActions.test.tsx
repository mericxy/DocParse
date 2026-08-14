import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import { ReviewActions } from "./ReviewActions";

it("does not silently download an older value while local changes are dirty", async () => {
  const user = userEvent.setup();
  const onDownload = vi.fn();
  render(
    <ReviewActions
      dirty
      saving={false}
      downloading={null}
      feedback={null}
      onSave={vi.fn()}
      onDownload={onDownload}
    />,
  );

  expect(screen.getByText("Alterações não salvas")).toBeInTheDocument();
  for (const label of ["Baixar XLSX", "Baixar CSV", "Baixar JSON"]) {
    expect(screen.getByRole("button", { name: label })).toBeDisabled();
  }
  await user.click(screen.getByRole("button", { name: "Baixar XLSX" }));
  expect(onDownload).not.toHaveBeenCalled();
});

it("enables downloads after the value is saved", async () => {
  const user = userEvent.setup();
  const onDownload = vi.fn();
  render(
    <ReviewActions
      dirty={false}
      saving={false}
      downloading={null}
      feedback="Correções salvas."
      onSave={vi.fn()}
      onDownload={onDownload}
    />,
  );

  await user.click(screen.getByRole("button", { name: "Baixar JSON" }));
  expect(onDownload).toHaveBeenCalledWith("json");
  expect(screen.getByRole("button", { name: "Salvar correções" })).toHaveClass("toolbar-button");
  expect(screen.getByRole("button", { name: "Baixar XLSX" })).toHaveClass("toolbar-button", "download-button", "download-xlsx");
  expect(screen.getByRole("button", { name: "Baixar CSV" })).toHaveClass("toolbar-button", "download-button", "download-csv");
  expect(screen.getByRole("button", { name: "Baixar JSON" })).toHaveClass("toolbar-button", "download-button", "download-json");
});
