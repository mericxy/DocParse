import { useEffect, useRef, useState } from "react";

import {
  ApiError,
  createTranscription,
  fetchExport,
  pollTranscription,
  updateTranscription,
} from "./api/transcriptions";
import { ProcessingView } from "./components/ProcessingView";
import { ReviewWorkspace } from "./components/ReviewWorkspace";
import { UploadPanel } from "./components/UploadPanel";
import {
  loadExampleDocument,
  type ExampleDocument,
} from "./examples/documents";
import type {
  DocumentType,
  ExportFormat,
  TranscriptionValue,
} from "./types/transcription";

type ViewState = "upload" | "sending" | "processing" | "review" | "error";

function publicError(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "Não foi possível concluir a operação.";
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export default function App() {
  const [type, setType] = useState<DocumentType>("cartao-ponto");
  const [file, setFile] = useState<File | null>(null);
  const [selectedExample, setSelectedExample] = useState<ExampleDocument | null>(null);
  const [loadingExample, setLoadingExample] = useState<string | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [view, setView] = useState<ViewState>("upload");
  const [jobId, setJobId] = useState<string | null>(null);
  const [draft, setDraft] = useState<TranscriptionValue | null>(null);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState<ExportFormat | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const requestController = useRef<AbortController | null>(null);
  const exampleController = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      requestController.current?.abort();
      exampleController.current?.abort();
    };
  }, []);

  useEffect(() => {
    return () => {
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    };
  }, [pdfUrl]);

  function selectFile(nextFile: File | null) {
    setFile(nextFile);
    setError(null);
    setPdfUrl(nextFile ? URL.createObjectURL(nextFile) : null);
  }

  function selectLocalFile(nextFile: File | null) {
    exampleController.current?.abort();
    setLoadingExample(null);
    setSelectedExample(null);
    selectFile(nextFile);
  }

  function selectType(nextType: DocumentType) {
    if (selectedExample && selectedExample.type !== nextType) {
      setSelectedExample(null);
      selectFile(null);
    }
    setType(nextType);
  }

  async function selectExample(example: ExampleDocument) {
    exampleController.current?.abort();
    const controller = new AbortController();
    exampleController.current = controller;
    setLoadingExample(example.filename);
    setError(null);
    try {
      const exampleFile = await loadExampleDocument(example, controller.signal);
      setType(example.type);
      setSelectedExample(example);
      selectFile(exampleFile);
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      setError(publicError(caught));
    } finally {
      if (exampleController.current === controller) setLoadingExample(null);
    }
  }

  async function submit() {
    if (!file) return;
    requestController.current?.abort();
    const controller = new AbortController();
    requestController.current = controller;
    setError(null);
    setFeedback(null);
    setView("sending");

    try {
      const created = await createTranscription(file, type, controller.signal);
      setJobId(created.id);
      setView("processing");
      const terminal = await pollTranscription(created.id, {
        signal: controller.signal,
        onUpdate: (response) => {
          if (response.status === "processando") setView("processing");
        },
      });
      if (terminal.status === "erro") {
        throw new Error(terminal.erro ?? "O processamento terminou com erro.");
      }
      if (!terminal.value) {
        throw new Error("O processamento terminou sem uma transcrição.");
      }
      setType(terminal.tipo);
      setDraft(structuredClone(terminal.value));
      setDirty(false);
      setFeedback("Resultado recebido e pronto para revisão.");
      setView("review");
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") return;
      setError(publicError(caught));
      setView("error");
    }
  }

  function changeDraft(value: TranscriptionValue) {
    setDraft(value);
    setDirty(true);
    setFeedback(null);
  }

  async function save() {
    if (!jobId || !draft || !dirty) return;
    setSaving(true);
    setError(null);
    try {
      const response = await updateTranscription(jobId, draft);
      if (!response.value) throw new Error("A API não retornou o valor salvo.");
      setDraft(structuredClone(response.value));
      setDirty(false);
      setFeedback("Correções salvas. Os downloads já usam esta versão.");
    } catch (caught) {
      setError(publicError(caught));
    } finally {
      setSaving(false);
    }
  }

  async function download(format: ExportFormat) {
    if (!jobId || dirty) return;
    setDownloading(format);
    setError(null);
    try {
      const exported = await fetchExport(jobId, format);
      saveBlob(exported.blob, exported.filename);
      setFeedback(`${format.toUpperCase()} gerado com a versão salva.`);
    } catch (caught) {
      setError(publicError(caught));
    } finally {
      setDownloading(null);
    }
  }

  function startOver() {
    if (dirty && !window.confirm("Descartar as alterações ainda não salvas?")) return;
    requestController.current?.abort();
    exampleController.current?.abort();
    setFile(null);
    setSelectedExample(null);
    setLoadingExample(null);
    setPdfUrl(null);
    setJobId(null);
    setDraft(null);
    setDirty(false);
    setError(null);
    setFeedback(null);
    setView("upload");
  }

  const isBusy = view === "sending" || view === "processing";

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand" aria-label="DocParse">
          <span><strong>DocParse</strong><small>Revisão de documentos</small></span>
        </div>
        <div className="header-meta">
          {view !== "upload" && (
            <button className="header-button" onClick={startOver} type="button">Novo documento</button>
          )}
        </div>
      </header>

      <div className="app-content">
        {(view === "upload" || view === "sending" || view === "error") && (
          <UploadPanel
            file={file}
            type={type}
            busy={view === "sending"}
            loadingExample={loadingExample}
            selectedExample={selectedExample}
            error={error}
            onFile={selectLocalFile}
            onExample={selectExample}
            onType={selectType}
            onSubmit={submit}
          />
        )}

        {view === "processing" && file && pdfUrl && jobId && (
          <ProcessingView pdfUrl={pdfUrl} filename={file.name} jobId={jobId} />
        )}

        {view === "review" && file && pdfUrl && draft && (
          <ReviewWorkspace
            type={type}
            value={draft}
            pdfUrl={pdfUrl}
            filename={file.name}
            dirty={dirty}
            saving={saving}
            downloading={downloading}
            feedback={feedback}
            onChange={changeDraft}
            onSave={save}
            onDownload={download}
          />
        )}
      </div>

      {error && view === "review" && <div className="floating-error" role="alert">{error}</div>}
      <footer>
        <a
          className="footer-author"
          href="https://github.com/mericxy"
          target="_blank"
          rel="noopener noreferrer"
        >
          <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false">
            <path
              fill="currentColor"
              d="M12 .7a11.5 11.5 0 0 0-3.64 22.4c.58.11.79-.25.79-.56v-2.23c-3.23.7-3.91-1.37-3.91-1.37-.53-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.71.08-.71 1.17.08 1.78 1.2 1.78 1.2 1.04 1.78 2.72 1.27 3.38.97.1-.75.4-1.27.74-1.56-2.58-.29-5.29-1.29-5.29-5.69 0-1.26.45-2.29 1.19-3.09-.12-.29-.52-1.47.11-3.05 0 0 .97-.31 3.16 1.18a10.9 10.9 0 0 1 5.76 0c2.2-1.49 3.16-1.18 3.16-1.18.63 1.58.23 2.76.11 3.05.74.8 1.19 1.83 1.19 3.09 0 4.42-2.72 5.39-5.31 5.68.42.36.79 1.07.79 2.16v3.25c0 .31.21.68.8.56A11.5 11.5 0 0 0 12 .7Z"
            />
          </svg>
          <span>Feito por mericxy</span>
        </a>
      </footer>
    </div>
  );
}
