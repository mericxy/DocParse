import type {
  CreatedTranscription,
  DocumentType,
  ExportFormat,
  TranscriptionResponse,
  TranscriptionValue,
} from "../types/transcription";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function responseMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail
        .map((item) =>
          typeof item === "object" && item && "msg" in item
            ? String(item.msg)
            : "Dado inválido",
        )
        .join("; ");
    }
  } catch {
    // Fall through to a stable public message.
  }
  return `A solicitação falhou (HTTP ${response.status}).`;
}

async function requestJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    throw new ApiError(await responseMessage(response), response.status);
  }
  return (await response.json()) as T;
}

export async function createTranscription(
  file: File,
  type: DocumentType,
  signal?: AbortSignal,
): Promise<CreatedTranscription> {
  const form = new FormData();
  form.append("arquivo", file);
  form.append("tipo", type);
  return requestJson<CreatedTranscription>("/api/transcricoes", {
    method: "POST",
    body: form,
    signal,
  });
}

export function getTranscription(
  id: string,
  signal?: AbortSignal,
): Promise<TranscriptionResponse> {
  return requestJson<TranscriptionResponse>(`/api/transcricoes/${id}`, {
    signal,
  });
}

export function updateTranscription(
  id: string,
  value: TranscriptionValue,
  signal?: AbortSignal,
): Promise<TranscriptionResponse> {
  return requestJson<TranscriptionResponse>(`/api/transcricoes/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value }),
    signal,
  });
}

function wait(milliseconds: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Operação cancelada", "AbortError"));
      return;
    }
    const timeout = window.setTimeout(resolve, milliseconds);
    signal?.addEventListener(
      "abort",
      () => {
        window.clearTimeout(timeout);
        reject(new DOMException("Operação cancelada", "AbortError"));
      },
      { once: true },
    );
  });
}

interface PollOptions {
  signal?: AbortSignal;
  intervalMs?: number;
  onUpdate?: (response: TranscriptionResponse) => void;
  getStatus?: (
    id: string,
    signal?: AbortSignal,
  ) => Promise<TranscriptionResponse>;
  waitForNext?: (milliseconds: number, signal?: AbortSignal) => Promise<void>;
}

export async function pollTranscription(
  id: string,
  options: PollOptions = {},
): Promise<TranscriptionResponse> {
  const {
    signal,
    intervalMs = 1_200,
    onUpdate,
    getStatus = getTranscription,
    waitForNext = wait,
  } = options;

  while (true) {
    const response = await getStatus(id, signal);
    onUpdate?.(response);
    if (response.status !== "processando") return response;
    await waitForNext(intervalMs, signal);
  }
}

export async function fetchExport(
  id: string,
  format: ExportFormat,
): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(
    `${API_BASE}/api/transcricoes/${id}/planilha?formato=${format}`,
  );
  if (!response.ok) {
    throw new ApiError(await responseMessage(response), response.status);
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^";]+)"?/i.exec(disposition);
  return {
    blob: await response.blob(),
    filename: match?.[1] ?? `transcricao-${id}.${format}`,
  };
}
