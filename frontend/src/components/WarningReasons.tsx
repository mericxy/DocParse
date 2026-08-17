import type { RowWarning } from "../review/warnings";

interface WarningReasonsProps {
  warning: RowWarning;
  compact?: boolean;
}

export function WarningReasons({ warning, compact = false }: WarningReasonsProps) {
  if (!warning.reasons.length) {
    return <span className="no-warning" aria-label="Sem alerta">—</span>;
  }
  if (compact) {
    const description = warning.reasons.join("; ");
    return (
      <span
        className="warning-indicator"
        tabIndex={0}
        aria-label={`Advertências: ${description}`}
      >
        <span aria-hidden="true">⚠</span>
        <span className="warning-tooltip" role="tooltip">
          {warning.reasons.map((reason) => <span key={reason}>{reason}</span>)}
        </span>
      </span>
    );
  }
  return (
    <div className="warning-list" aria-label="Advertências da linha">
      {warning.reasons.map((reason) => (
        <span className="warning-chip" key={reason}>
          {reason}
        </span>
      ))}
    </div>
  );
}
