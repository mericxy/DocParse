import { PdfViewer } from "./PdfViewer";

interface ProcessingViewProps {
  pdfUrl: string;
  filename: string;
  jobId: string;
}

export function ProcessingView({ pdfUrl, filename, jobId }: ProcessingViewProps) {
  return (
    <main className="workspace processing-workspace">
      <PdfViewer url={pdfUrl} filename={filename} />
      <section className="processing-panel" aria-live="polite">
        <span className="processing-orbit" aria-hidden="true"><i /></span>
        <span className="eyebrow">Processamento assíncrono</span>
        <h1>Lendo o documento…</h1>
        <p>
          Você pode continuar nesta tela. O status é consultado automaticamente e
          a revisão aparecerá assim que a extração terminar.
        </p>
        <div className="indeterminate-track"><span /></div>
        <dl className="job-meta">
          <div><dt>Status</dt><dd>Processando</dd></div>
          <div><dt>Identificador</dt><dd>{jobId.slice(0, 8)}…</dd></div>
        </dl>
        <p className="muted">Não exibimos percentual porque a API informa apenas o estado atual.</p>
      </section>
    </main>
  );
}
