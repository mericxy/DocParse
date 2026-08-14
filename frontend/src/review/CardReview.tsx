import { useMemo } from "react";

import { WarningReasons } from "../components/WarningReasons";
import type { CardValue, Punch } from "../types/transcription";
import { normalizeEditedTime } from "./time";
import { cardReviewRows, maxPunchCount } from "./warnings";

interface CardReviewProps {
  value: CardValue;
  onChange: (value: CardValue) => void;
}

function clone(value: CardValue): CardValue {
  return structuredClone(value);
}

export function CardReview({ value, onChange }: CardReviewProps) {
  const rows = useMemo(() => cardReviewRows(value), [value]);
  const punchCount = maxPunchCount(value);

  function updateDate(pageIndex: number, dayIndex: number, dateRaw: string) {
    const next = clone(value);
    next.pages[pageIndex].days[dayIndex].date_raw = dateRaw;
    onChange(next);
  }

  function updatePunch(pageIndex: number, dayIndex: number, punchIndex: number, text: string) {
    const next = clone(value);
    const punch = next.pages[pageIndex].days[dayIndex].punches[punchIndex];
    // Raw is always literal. The normalized field applies only the same safe,
    // explicit transformations already used by the backend extractor.
    punch.time_raw = text;
    punch.time_hhmm = normalizeEditedTime(text);
    onChange(next);
  }

  function addPunch(pageIndex: number, dayIndex: number) {
    const next = clone(value);
    const punches = next.pages[pageIndex].days[dayIndex].punches;
    const punch: Punch = {
      kind: punches.length % 2 === 0 ? "IN" : "OUT",
      time_raw: "",
      time_hhmm: "",
    };
    punches.push(punch);
    onChange(next);
  }

  function removeLastPunch(pageIndex: number, dayIndex: number) {
    const next = clone(value);
    next.pages[pageIndex].days[dayIndex].punches.pop();
    onChange(next);
  }

  return (
    <section aria-labelledby="card-review-heading">
      <h2 className="visually-hidden" id="card-review-heading">Dias e batidas</h2>
      <div className="table-scroll">
        <table className="review-table card-table">
          <thead>
            <tr>
              <th>Data</th>
              {Array.from({ length: punchCount }, (_, index) => (
                <th key={index}>{index % 2 === 0 ? `Entrada ${index / 2 + 1}` : `Saída ${(index + 1) / 2}`}</th>
              ))}
              <th>Advertências</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {value.pages.flatMap((page, pageIndex) => {
              const pageRows = rows.filter((row) => row.pageIndex === pageIndex);
              if (!pageRows.length) {
                return [
                  <FragmentWithPage
                    key={`empty-${pageIndex}`}
                    startsPage
                    page={page.page}
                    colSpan={punchCount + 3}
                  >
                    <tr className="warning-yellow empty-card-page">
                      <td className="first-data-cell" colSpan={punchCount + 3}>
                        <div className="empty-card-page-content">
                          <strong>Página {page.page} — nenhum dia extraído</strong>
                          <WarningReasons warning={{
                            severity: "yellow",
                            reasons: ["Página sem dias extraídos"],
                          }} />
                        </div>
                      </td>
                    </tr>
                  </FragmentWithPage>,
                ];
              }
              return pageRows.map((row, rowIndex) => (
                <FragmentWithPage
                  key={`${row.pageIndex}-${row.dayIndex}`}
                  startsPage={rowIndex === 0}
                  page={row.page}
                  colSpan={punchCount + 3}
                >
                  <tr className={`warning-${row.warning.severity}`}>
                    <td className="first-data-cell">
                      <input
                        aria-label={`Data da página ${row.page}, linha ${row.dayIndex + 1}`}
                        className="cell-input date-input"
                        value={row.day.date_raw}
                        onChange={(event) => updateDate(row.pageIndex, row.dayIndex, event.target.value)}
                      />
                    </td>
                    {Array.from({ length: punchCount }, (_, punchIndex) => {
                      const punch = row.day.punches[punchIndex];
                      if (punch) {
                        return (
                          <td key={punchIndex}>
                            <input
                              aria-label={`${punch.kind === "IN" ? "Entrada" : "Saída"} ${Math.floor(punchIndex / 2) + 1} de ${row.day.date_raw}`}
                              className="cell-input time-input"
                              value={punch.time_hhmm}
                              onChange={(event) => updatePunch(row.pageIndex, row.dayIndex, punchIndex, event.target.value)}
                            />
                            {punch.time_raw !== punch.time_hhmm && (
                              <small className="raw-value" title="Leitura original">raw: {punch.time_raw}</small>
                            )}
                          </td>
                        );
                      }
                      if (punchIndex === row.day.punches.length) {
                        return (
                          <td key={punchIndex}>
                            <button className="inline-add" type="button" onClick={() => addPunch(row.pageIndex, row.dayIndex)}>
                              + batida
                            </button>
                          </td>
                        );
                      }
                      return <td key={punchIndex}><span className="empty-cell">—</span></td>;
                    })}
                    <td className="warning-cell"><WarningReasons warning={row.warning} /></td>
                    <td>
                      <div className="row-actions">
                        <button className="icon-button" type="button" onClick={() => addPunch(row.pageIndex, row.dayIndex)}>Adicionar</button>
                        <button className="icon-button danger" type="button" disabled={!row.day.punches.length} onClick={() => removeLastPunch(row.pageIndex, row.dayIndex)}>Remover última</button>
                      </div>
                    </td>
                  </tr>
                </FragmentWithPage>
              ));
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

interface FragmentWithPageProps {
  startsPage: boolean;
  page: number;
  colSpan: number;
  children: React.ReactNode;
}

function FragmentWithPage({ startsPage, page, colSpan, children }: FragmentWithPageProps) {
  return (
    <>
      {startsPage && (
        <tr className="page-divider">
          <th colSpan={colSpan}>Página {page}</th>
        </tr>
      )}
      {children}
    </>
  );
}
