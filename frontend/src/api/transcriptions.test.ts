import { describe, expect, it, vi } from "vitest";

import { pollTranscription, updateTranscription } from "./transcriptions";
import type { CardValue, TranscriptionResponse } from "../types/transcription";

const pending: TranscriptionResponse = {
  id: "job-1",
  tipo: "cartao-ponto",
  status: "processando",
  erro: null,
  value: null,
};

const cardValue: CardValue = {
  pages: [{ page: 1, days: [{ date_raw: "01/01/2025", punches: [] }] }],
};

it("polling stops immediately when the job completes", async () => {
  const completed: TranscriptionResponse = {
    ...pending,
    status: "concluido",
    value: cardValue,
  };
  const getStatus = vi.fn()
    .mockResolvedValueOnce(pending)
    .mockResolvedValueOnce(completed);
  const waitForNext = vi.fn().mockResolvedValue(undefined);

  const result = await pollTranscription("job-1", { getStatus, waitForNext });

  expect(result).toEqual(completed);
  expect(getStatus).toHaveBeenCalledTimes(2);
  expect(waitForNext).toHaveBeenCalledTimes(1);
});

it("polling stops immediately and preserves the public error", async () => {
  const failed: TranscriptionResponse = {
    ...pending,
    status: "erro",
    erro: "Não foi possível processar o documento.",
  };
  const getStatus = vi.fn().mockResolvedValue(failed);
  const waitForNext = vi.fn();

  const result = await pollTranscription("job-1", { getStatus, waitForNext });

  expect(result).toEqual(failed);
  expect(getStatus).toHaveBeenCalledTimes(1);
  expect(waitForNext).not.toHaveBeenCalled();
});

it("polling can be aborted without leaving another status request scheduled", async () => {
  const controller = new AbortController();
  const getStatus = vi.fn().mockResolvedValue(pending);
  const waitForNext = vi.fn((_milliseconds: number, signal?: AbortSignal) => {
    controller.abort();
    return Promise.reject(new DOMException("Operação cancelada", "AbortError"));
  });

  await expect(
    pollTranscription("job-1", {
      signal: controller.signal,
      getStatus,
      waitForNext,
    }),
  ).rejects.toMatchObject({ name: "AbortError" });
  expect(getStatus).toHaveBeenCalledTimes(1);
  expect(waitForNext).toHaveBeenCalledTimes(1);
});

it("PUT sends only the complete updated value under the literal contract", async () => {
  const corrected: CardValue = {
    pages: [{ page: 1, days: [{ date_raw: "02/01/2025", punches: [] }] }],
  };
  const response: TranscriptionResponse = {
    ...pending,
    status: "concluido",
    value: corrected,
  };
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(response), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  await updateTranscription("job-1", corrected);

  const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(init.method).toBe("PUT");
  expect(JSON.parse(String(init.body))).toEqual({ value: corrected });
  expect(JSON.parse(String(init.body))).not.toHaveProperty("warning");
});
