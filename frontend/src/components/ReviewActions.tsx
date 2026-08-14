import type { ExportFormat } from "../types/transcription";

interface ReviewActionsProps {
  dirty: boolean;
  saving: boolean;
  downloading: ExportFormat | null;
  feedback: string | null;
  onSave: () => void;
  onDownload: (format: ExportFormat) => void;
}

export function ReviewActions({
  dirty,
  saving,
  downloading,
  feedback,
  onSave,
  onDownload,
}: ReviewActionsProps) {
  return (
    <div className="review-actions">
      <div className="save-state" aria-live="polite">
        <span className={dirty ? "dirty-dot" : "saved-dot"} />
        <div>
          <strong>{dirty ? "Alterações não salvas" : "Alterações salvas"}</strong>
          <small>
            {dirty
              ? "Salve antes de liberar os downloads."
              : feedback ?? "A planilha usará esta versão."}
          </small>
        </div>
      </div>
      <button className="primary-button toolbar-button" type="button" onClick={onSave} disabled={!dirty || saving}>
        {saving ? "Salvando…" : "Salvar correções"}
      </button>
      <div className="download-group" aria-label="Formatos para download">
        {(["xlsx", "csv", "json"] as ExportFormat[]).map((format) => (
          <button
            className={`toolbar-button download-button download-${format}`}
            disabled={dirty || saving || downloading !== null}
            key={format}
            onClick={() => onDownload(format)}
            type="button"
          >
            {downloading === format ? `Baixando ${format.toUpperCase()}…` : `Baixar ${format.toUpperCase()}`}
          </button>
        ))}
      </div>
    </div>
  );
}
