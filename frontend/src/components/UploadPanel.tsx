import type { FormEvent } from "react";

import { EXAMPLE_GROUPS, type ExampleDocument } from "../examples/documents";
import type { DocumentType } from "../types/transcription";

interface UploadPanelProps {
  file: File | null;
  type: DocumentType;
  busy: boolean;
  loadingExample: string | null;
  selectedExample: ExampleDocument | null;
  error: string | null;
  onFile: (file: File | null) => void;
  onExample: (example: ExampleDocument) => void;
  onType: (type: DocumentType) => void;
  onSubmit: () => void;
}

export function UploadPanel({
  file,
  type,
  busy,
  loadingExample,
  selectedExample,
  error,
  onFile,
  onExample,
  onType,
  onSubmit,
}: UploadPanelProps) {
  function submit(event: FormEvent) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <main className="upload-shell">
      <section className="intro-panel">
        <span className="eyebrow">Revisão assistida</span>
        <h1>Do documento bruto à planilha conferida.</h1>
        <p>
          Envie um cartão de ponto ou holerite. O processamento acontece fora da
          requisição e, quando terminar, você revisa cada dado com o PDF ao lado.
        </p>
        <ol className="flow-list" aria-label="Etapas do fluxo">
          <li><span>01</span> Envie o PDF</li>
          <li><span>02</span> Aguarde a leitura</li>
          <li><span>03</span> Revise e corrija</li>
          <li><span>04</span> Baixe o resultado</li>
        </ol>
      </section>

      <form className="upload-card" onSubmit={submit}>
        <div className="panel-heading upload-heading">
          <div>
            <span className="eyebrow">Novo documento</span>
            <h2>Comece a transcrição</h2>
            <small className="processing-note">Processamento local</small>
          </div>
        </div>

        <fieldset className="type-picker">
          <legend>Tipo de documento</legend>
          <label className={type === "cartao-ponto" ? "type-option selected" : "type-option"}>
            <input
              type="radio"
              name="document-type"
              value="cartao-ponto"
              checked={type === "cartao-ponto"}
              onChange={() => onType("cartao-ponto")}
            />
            <span><strong>Cartão de ponto</strong><small>Dias e batidas</small></span>
          </label>
          <label className={type === "holerite" ? "type-option selected" : "type-option"}>
            <input
              type="radio"
              name="document-type"
              value="holerite"
              checked={type === "holerite"}
              onChange={() => onType("holerite")}
            />
            <span><strong>Holerite</strong><small>Verbas e bases</small></span>
          </label>
        </fieldset>

        <label className="file-drop">
          <input
            type="file"
            accept="application/pdf,.pdf"
            onChange={(event) => onFile(event.target.files?.[0] ?? null)}
          />
          <span className="file-drop-mark">PDF</span>
          {file ? (
            <span className="file-copy">
              <strong>{file.name}</strong>
              <small>
                {selectedExample
                  ? `${selectedExample.label} · exemplo incluído no projeto · clique para trocar`
                  : `${(file.size / 1024 / 1024).toFixed(2)} MB · clique para trocar`}
              </small>
            </span>
          ) : (
            <span className="file-copy">
              <strong>Selecione um arquivo PDF</strong>
              <small>Limite padrão do servidor: 10 MB</small>
            </span>
          )}
        </label>

        <div className="example-divider" aria-hidden="true"><span>ou</span></div>
        <details className="example-picker">
          <summary>Testar com um exemplo</summary>
          <div className="example-groups">
            {EXAMPLE_GROUPS.map((group) => (
              <section key={group.type} aria-labelledby={`examples-${group.type}`}>
                <h3 id={`examples-${group.type}`}>{group.label}</h3>
                <div className="example-options">
                  {group.documents.map((example) => (
                    <button
                      className={selectedExample?.filename === example.filename ? "example-option selected" : "example-option"}
                      disabled={busy || loadingExample !== null}
                      key={example.filename}
                      onClick={() => onExample(example)}
                      type="button"
                    >
                      <span>{example.label}</span>
                      <small>{example.filename}</small>
                      {loadingExample === example.filename && <span className="visually-hidden">Carregando</span>}
                    </button>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </details>

        {error && <div className="message error-message" role="alert">{error}</div>}

        <button className="primary-button upload-button" disabled={!file || busy} type="submit">
          {busy ? <span className="spinner" aria-hidden="true" /> : null}
          {busy ? "Enviando…" : "Enviar para processamento"}
        </button>
        <p className="form-footnote">
          O nome original não é persistido nos logs. O arquivo é removido pela
          política de retenção do serviço.
        </p>
      </form>
    </main>
  );
}
