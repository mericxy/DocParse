interface PdfViewerProps {
  url: string;
  filename: string;
  onHide?: () => void;
  onShowData?: () => void;
}

export function PdfViewer({ url, filename, onHide, onShowData }: PdfViewerProps) {
  return (
    <section className="pdf-panel" aria-labelledby="pdf-heading">
      <div className="panel-heading">
        <div className="panel-title">
          <h2 id="pdf-heading">PDF original</h2>
          <span className="file-pill" title={filename}>Arquivo local</span>
        </div>
        <div className="panel-actions">
          <a className="panel-action" href={url} target="_blank" rel="noopener noreferrer">
            Abrir em nova guia
          </a>
          {onShowData && (
            <button className="panel-action" type="button" onClick={onShowData}>Mostrar dados</button>
          )}
          {onHide && (
            <button className="panel-action" type="button" onClick={onHide}>Ocultar PDF</button>
          )}
        </div>
      </div>
      <div className="pdf-body">
        <iframe className="pdf-frame" src={url} title={`Visualização de ${filename}`} />
      </div>
    </section>
  );
}
