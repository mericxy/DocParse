import { useMemo, useState } from "react";

import type {
  CardValue,
  DocumentType,
  ExportFormat,
  PayrollValue,
  TranscriptionValue,
} from "../types/transcription";
import { CardReview } from "../review/CardReview";
import { PayrollReview } from "../review/PayrollReview";
import { cardReviewRows, payrollReviewRows, type RowWarning } from "../review/warnings";
import { PdfViewer } from "./PdfViewer";
import { ReviewActions } from "./ReviewActions";
import { WarningReasons } from "./WarningReasons";

interface ReviewWorkspaceProps {
  type: DocumentType;
  value: TranscriptionValue;
  pdfUrl: string;
  filename: string;
  dirty: boolean;
  saving: boolean;
  downloading: ExportFormat | null;
  feedback: string | null;
  onChange: (value: TranscriptionValue) => void;
  onSave: () => void;
  onDownload: (format: ExportFormat) => void;
}

function documentWarnings(type: DocumentType, value: TranscriptionValue): RowWarning {
  const reasons: string[] = [];
  let hasRedWarning = false;
  const addReason = (reason: string) => {
    if (!reasons.includes(reason)) reasons.push(reason);
  };

  if (type === "cartao-ponto") {
    const card = value as CardValue;
    if (card.pages.length > 0 && card.pages.every((page) => !page.days.length)) {
      addReason("Nenhuma linha pôde ser transcrita com segurança.");
      addReason("O documento foi processado, mas os downloads refletirão uma transcrição sem dias. Revise o PDF antes de continuar.");
    }
    for (const row of cardReviewRows(card)) {
      row.warning.reasons.forEach(addReason);
      if (row.warning.severity === "red") hasRedWarning = true;
    }
  } else {
    const payroll = value as PayrollValue;
    const hasRepeatedLabels = payroll.pages.some((page) => {
      const seen = new Set<string>();
      return page.fields.some((field) => {
        if (seen.has(field.label)) return true;
        seen.add(field.label);
        return false;
      });
    });
    if (hasRepeatedLabels) {
      addReason("Há verbas repetidas na mesma competência.");
      addReason("O JSON preserva todas as ocorrências. CSV e XLSX serão recusados porque uma única coluna por label não consegue representá-las sem perder valores.");
    }
    for (const row of payrollReviewRows(payroll)) {
      row.warning.reasons.forEach(addReason);
      if (row.warning.severity === "red") hasRedWarning = true;
    }
  }

  return {
    severity: hasRedWarning ? "red" : reasons.length ? "yellow" : "none",
    reasons,
  };
}

export function ReviewWorkspace({
  type,
  value,
  pdfUrl,
  filename,
  dirty,
  saving,
  downloading,
  feedback,
  onChange,
  onSave,
  onDownload,
}: ReviewWorkspaceProps) {
  const [visiblePanel, setVisiblePanel] = useState<"both" | "pdf" | "data">("both");
  const dataTitle = type === "cartao-ponto" ? "Dados do cartão" : "Dados do holerite";
  const warnings = useMemo(() => documentWarnings(type, value), [type, value]);

  return (
    <main className="review-page">
      <ReviewActions
        dirty={dirty}
        saving={saving}
        downloading={downloading}
        feedback={feedback}
        onSave={onSave}
        onDownload={onDownload}
      />
      <div className={`workspace review-workspace panels-${visiblePanel}`}>
        {visiblePanel !== "data" && (
          <PdfViewer
            url={pdfUrl}
            filename={filename}
            onHide={visiblePanel === "both" ? () => setVisiblePanel("data") : undefined}
            onShowData={visiblePanel === "pdf" ? () => setVisiblePanel("both") : undefined}
          />
        )}
        {visiblePanel !== "pdf" && (
          <section className="transcription-panel" aria-label="Transcrição editável">
            <div className="panel-heading data-panel-heading">
              <div className="panel-title">
                <h2>{dataTitle}</h2>
              </div>
              <div className="panel-actions">
                {warnings.reasons.length > 0 && (
                  <span className="panel-warning">
                    <WarningReasons warning={warnings} compact />
                  </span>
                )}
                {visiblePanel === "data" && (
                  <button className="panel-action" type="button" onClick={() => setVisiblePanel("both")}>
                    Mostrar PDF
                  </button>
                )}
                {visiblePanel === "both" && (
                  <button className="panel-action" type="button" onClick={() => setVisiblePanel("pdf")}>
                    Ocultar dados
                  </button>
                )}
              </div>
            </div>
            <div className="transcription-body">
              {type === "cartao-ponto" ? (
                <CardReview value={value as CardValue} onChange={onChange} />
              ) : (
                <PayrollReview value={value as PayrollValue} onChange={onChange} />
              )}
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
