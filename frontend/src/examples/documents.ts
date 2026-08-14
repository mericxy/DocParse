import type { DocumentType } from "../types/transcription";

export interface ExampleDocument {
  filename: string;
  label: string;
  type: DocumentType;
}

export interface ExampleGroup {
  label: string;
  type: DocumentType;
  documents: ExampleDocument[];
}

function examples(
  type: DocumentType,
  labelPrefix: string,
  filenamePrefix: string,
): ExampleDocument[] {
  return [1, 2, 3, 4].map((number) => {
    const suffix = String(number).padStart(2, "0");
    return {
      filename: `${filenamePrefix}-${suffix}.pdf`,
      label: `${labelPrefix} ${suffix}`,
      type,
    };
  });
}

export const EXAMPLE_GROUPS: ExampleGroup[] = [
  {
    label: "Cartão de ponto",
    type: "cartao-ponto",
    documents: examples("cartao-ponto", "Cartão de ponto", "time-card"),
  },
  {
    label: "Holerite",
    type: "holerite",
    documents: examples("holerite", "Holerite", "payroll"),
  },
];

export async function loadExampleDocument(
  example: ExampleDocument,
  signal?: AbortSignal,
): Promise<File> {
  const response = await fetch(`/examples/${encodeURIComponent(example.filename)}`, {
    signal,
  });
  if (!response.ok) {
    throw new Error("Não foi possível carregar este documento de exemplo.");
  }

  const blob = await response.blob();
  const contentType = response.headers.get("Content-Type") ?? blob.type;
  if (blob.size === 0 || !contentType.toLowerCase().includes("application/pdf")) {
    throw new Error("Não foi possível carregar este documento de exemplo.");
  }

  return new File([blob], example.filename, { type: "application/pdf" });
}
