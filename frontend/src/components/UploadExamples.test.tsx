import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import App from "../App";

function pdfResponse(): Response {
  return new Response(new Blob(["%PDF-1.7\nexample"], { type: "application/pdf" }), {
    status: 200,
    headers: { "Content-Type": "application/pdf" },
  });
}

beforeEach(() => {
  vi.stubGlobal("URL", {
    createObjectURL: vi.fn(() => "blob:example-pdf"),
    revokeObjectURL: vi.fn(),
  });
});

it("lists the four time cards and four payroll examples in compact groups", async () => {
  const user = userEvent.setup();
  render(<App />);

  await user.click(screen.getByText("Testar com um exemplo"));

  expect(screen.getByRole("heading", { name: "Cartão de ponto" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Holerite" })).toBeInTheDocument();
  for (const filename of [
    "time-card-01.pdf",
    "time-card-02.pdf",
    "time-card-03.pdf",
    "time-card-04.pdf",
    "payroll-01.pdf",
    "payroll-02.pdf",
    "payroll-03.pdf",
    "payroll-04.pdf",
  ]) {
    expect(screen.getByText(filename)).toBeInTheDocument();
  }
});

it("selecting a time-card example automatically selects the card type", async () => {
  const user = userEvent.setup();
  const fetchMock = vi.fn().mockResolvedValue(pdfResponse());
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);

  await user.click(screen.getByRole("radio", { name: /Holerite/ }));
  await user.click(screen.getByText("Testar com um exemplo"));
  await user.click(screen.getByRole("button", { name: /Cartão de ponto 02/ }));

  expect(await screen.findByText(/Cartão de ponto 02 · exemplo incluído no projeto/)).toBeInTheDocument();
  expect(screen.getByRole("radio", { name: /Cartão de ponto/ })).toBeChecked();
  expect(fetchMock).toHaveBeenCalledWith(
    "/examples/time-card-02.pdf",
    expect.objectContaining({ signal: expect.any(AbortSignal) }),
  );
});

it("submits a payroll example through the normal multipart upload", async () => {
  const user = userEvent.setup();
  const completed = {
    id: "job-example",
    tipo: "holerite",
    status: "concluido",
    erro: null,
    value: {
      pages: [
        {
          page: 1,
          year: "2019",
          month: "10",
          fields: [],
          bases: [],
        },
      ],
    },
  };
  const fetchMock = vi.fn().mockImplementation((input: string, init?: RequestInit) => {
    if (input === "/examples/payroll-03.pdf") return Promise.resolve(pdfResponse());
    if (input === "/api/transcricoes" && init?.method === "POST") {
      return Promise.resolve(
        new Response(JSON.stringify({ id: "job-example" }), {
          status: 202,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }
    if (input === "/api/transcricoes/job-example") {
      return Promise.resolve(
        new Response(JSON.stringify(completed), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }
    throw new Error(`Unexpected request: ${input}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<App />);

  await user.click(screen.getByText("Testar com um exemplo"));
  await user.click(screen.getByRole("button", { name: /Holerite 03/ }));
  expect(await screen.findByText(/Holerite 03 · exemplo incluído no projeto/)).toBeInTheDocument();
  expect(screen.getByRole("radio", { name: /Holerite/ })).toBeChecked();

  await user.click(screen.getByRole("button", { name: "Enviar para processamento" }));
  expect(await screen.findByRole("heading", { name: "Dados do holerite" })).toBeInTheDocument();

  const postCall = fetchMock.mock.calls.find(
    ([input, init]) => input === "/api/transcricoes" && init?.method === "POST",
  );
  expect(postCall).toBeDefined();
  const form = postCall?.[1]?.body as FormData;
  const uploaded = form.get("arquivo") as File;
  expect(uploaded).toBeInstanceOf(File);
  expect(uploaded.name).toBe("payroll-03.pdf");
  expect(form.get("tipo")).toBe("holerite");
  expect(fetchMock.mock.calls.filter(([input]) => input === "/examples/payroll-03.pdf")).toHaveLength(1);
});

it("shows a public error and does not select an unavailable example", async () => {
  const user = userEvent.setup();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 404 })));
  render(<App />);

  await user.click(screen.getByText("Testar com um exemplo"));
  await user.click(screen.getByRole("button", { name: /Holerite 04/ }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Não foi possível carregar este documento de exemplo.",
  );
  expect(screen.getByRole("button", { name: "Enviar para processamento" })).toBeDisabled();
  expect(screen.getByText("Selecione um arquivo PDF")).toBeInTheDocument();
});
