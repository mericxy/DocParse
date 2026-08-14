import { useMemo } from "react";

import { WarningReasons } from "../components/WarningReasons";
import type { PayrollField, PayrollValue } from "../types/transcription";
import { payrollFieldLabels, payrollReviewRows } from "./warnings";

interface PayrollReviewProps {
  value: PayrollValue;
  onChange: (value: PayrollValue) => void;
}

function clone(value: PayrollValue): PayrollValue {
  return structuredClone(value);
}

export function PayrollReview({ value, onChange }: PayrollReviewProps) {
  const labels = useMemo(() => payrollFieldLabels(value), [value]);
  const rows = useMemo(() => payrollReviewRows(value), [value]);

  function updateCompetence(pageIndex: number, key: "month" | "year", text: string) {
    const next = clone(value);
    next.pages[pageIndex][key] = text;
    onChange(next);
  }

  function updateField(
    pageIndex: number,
    fieldIndex: number,
    key: keyof PayrollField,
    text: string,
  ) {
    const next = clone(value);
    next.pages[pageIndex].fields[fieldIndex][key] = text;
    onChange(next);
  }

  function addKnownField(pageIndex: number, label: string) {
    const next = clone(value);
    const field: PayrollField = { code: "", label, reference: "", value: "" };
    next.pages[pageIndex].fields.push(field);
    onChange(next);
  }

  function updateBase(pageIndex: number, baseIndex: number, key: "label" | "value", text: string) {
    const next = clone(value);
    next.pages[pageIndex].bases[baseIndex][key] = text;
    onChange(next);
  }

  function addBase(pageIndex: number) {
    const next = clone(value);
    next.pages[pageIndex].bases.push({ label: "", value: "" });
    onChange(next);
  }

  function removeBase(pageIndex: number, baseIndex: number) {
    const next = clone(value);
    next.pages[pageIndex].bases.splice(baseIndex, 1);
    onChange(next);
  }

  return (
    <section aria-labelledby="payroll-review-heading">
      <h2 className="visually-hidden" id="payroll-review-heading">Competências e verbas</h2>
      <div className="table-scroll">
        <table className="review-table payroll-table" aria-label="Verbas do holerite">
          <thead>
            <tr>
              <th>Pág.</th>
              <th>Mês</th>
              <th>Ano</th>
              {labels.map((label) => <th key={label}>{label}</th>)}
              <th className="compact-warning-header">
                <span aria-hidden="true">⚠</span>
                <span className="visually-hidden">Advertências</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <PayrollRows
                key={row.pageIndex}
                row={row}
                labels={labels}
                colSpan={labels.length + 4}
                onCompetence={updateCompetence}
                onField={updateField}
                onAddField={addKnownField}
                onBase={updateBase}
                onAddBase={addBase}
                onRemoveBase={removeBase}
              />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

interface PayrollRowsProps {
  row: ReturnType<typeof payrollReviewRows>[number];
  labels: string[];
  colSpan: number;
  onCompetence: (pageIndex: number, key: "month" | "year", text: string) => void;
  onField: (
    pageIndex: number,
    fieldIndex: number,
    key: keyof PayrollField,
    text: string,
  ) => void;
  onAddField: (pageIndex: number, label: string) => void;
  onBase: (pageIndex: number, baseIndex: number, key: "label" | "value", text: string) => void;
  onAddBase: (pageIndex: number) => void;
  onRemoveBase: (pageIndex: number, baseIndex: number) => void;
}

function PayrollRows({
  row,
  labels,
  colSpan,
  onCompetence,
  onField,
  onAddField,
  onBase,
  onAddBase,
  onRemoveBase,
}: PayrollRowsProps) {
  return (
    <>
      <tr className={`warning-${row.warning.severity}`}>
        <td className="first-data-cell page-number">{row.page.page}</td>
        <td>
          <input
            aria-label={`Mês da linha ${row.pageIndex + 1}`}
            className="cell-input compact-input"
            value={row.page.month}
            onChange={(event) => onCompetence(row.pageIndex, "month", event.target.value)}
          />
        </td>
        <td>
          <input
            aria-label={`Ano da linha ${row.pageIndex + 1}`}
            className="cell-input year-input"
            value={row.page.year}
            onChange={(event) => onCompetence(row.pageIndex, "year", event.target.value)}
          />
        </td>
        {labels.map((label) => {
          const matches = row.page.fields
            .map((field, fieldIndex) => ({ field, fieldIndex }))
            .filter(({ field }) => field.label === label);
          return (
            <td key={label} className="field-cell">
              {matches.length > 1 && <span className="duplicate-badge">{matches.length} registros</span>}
              {matches.map(({ field, fieldIndex }, occurrence) => (
                <div className="field-editor" key={fieldIndex}>
                  {(field.code || field.reference || matches.length > 1) && (
                    <small>
                      {field.code ? `cód. ${field.code}` : `item ${occurrence + 1}`}
                      {field.reference ? ` · ref. ${field.reference}` : ""}
                    </small>
                  )}
                  <input
                    aria-label={`Valor da verba ${fieldIndex + 1}, linha ${row.pageIndex + 1}`}
                    className="cell-input money-input"
                    value={field.value}
                    onChange={(event) => onField(row.pageIndex, fieldIndex, "value", event.target.value)}
                  />
                  <details className="field-details">
                    <summary>Editar verba</summary>
                    <div className="field-details-grid">
                      <input
                        aria-label={`Código da verba ${fieldIndex + 1}, linha ${row.pageIndex + 1}`}
                        className="cell-input"
                        placeholder="Código"
                        value={field.code}
                        onChange={(event) => onField(row.pageIndex, fieldIndex, "code", event.target.value)}
                      />
                      <input
                        aria-label={`Label da verba ${fieldIndex + 1}, linha ${row.pageIndex + 1}`}
                        className="cell-input"
                        placeholder="Descrição"
                        value={field.label}
                        onChange={(event) => onField(row.pageIndex, fieldIndex, "label", event.target.value)}
                      />
                      <input
                        aria-label={`Referência da verba ${fieldIndex + 1}, linha ${row.pageIndex + 1}`}
                        className="cell-input"
                        placeholder="Referência"
                        value={field.reference}
                        onChange={(event) => onField(row.pageIndex, fieldIndex, "reference", event.target.value)}
                      />
                    </div>
                  </details>
                </div>
              ))}
              {!matches.length && (
                <button className="inline-add" type="button" onClick={() => onAddField(row.pageIndex, label)}>
                  + adicionar
                </button>
              )}
            </td>
          );
        })}
        <td className="warning-cell compact-warning-cell"><WarningReasons warning={row.warning} compact /></td>
      </tr>
      <tr className="bases-row">
        <td colSpan={colSpan}>
          <details>
            <summary>
              Bases e totais <span>{row.page.bases.length} registros</span>
            </summary>
            <div className="bases-editor">
              <div className="bases-subtable-scroll">
                <table
                  className="bases-subtable"
                  aria-label={`Bases e totais da linha ${row.pageIndex + 1}`}
                >
                  <thead>
                    <tr>
                      <th>Descrição</th>
                      <th>Valor</th>
                      <th>Ação</th>
                    </tr>
                  </thead>
                  <tbody>
                    {row.page.bases.map((base, baseIndex) => (
                      <tr key={baseIndex}>
                        <td>
                          <input
                            aria-label={`Label da base ${baseIndex + 1}, linha ${row.pageIndex + 1}`}
                            className="cell-input"
                            placeholder="Nome da base"
                            value={base.label}
                            onChange={(event) => onBase(row.pageIndex, baseIndex, "label", event.target.value)}
                          />
                        </td>
                        <td>
                          <input
                            aria-label={`Valor da base ${baseIndex + 1}, linha ${row.pageIndex + 1}`}
                            className="cell-input money-input"
                            placeholder="Valor"
                            value={base.value}
                            onChange={(event) => onBase(row.pageIndex, baseIndex, "value", event.target.value)}
                          />
                        </td>
                        <td>
                          <button className="icon-button danger" type="button" onClick={() => onRemoveBase(row.pageIndex, baseIndex)}>
                            Remover
                          </button>
                        </td>
                      </tr>
                    ))}
                    {!row.page.bases.length && (
                      <tr>
                        <td className="bases-empty" colSpan={3}>Nenhuma base extraída nesta linha.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              <button className="inline-add" type="button" onClick={() => onAddBase(row.pageIndex)}>+ adicionar base</button>
            </div>
          </details>
        </td>
      </tr>
    </>
  );
}
