export type DocumentType = "cartao-ponto" | "holerite";
export type TranscriptionStatus = "processando" | "concluido" | "erro";
export type ExportFormat = "xlsx" | "csv" | "json";

export interface Punch {
  kind: "IN" | "OUT";
  time_raw: string;
  time_hhmm: string;
}

export interface Day {
  date_raw: string;
  punches: Punch[];
}

export interface CardPage {
  page: number;
  days: Day[];
}

export interface CardValue {
  pages: CardPage[];
}

export interface PayrollField {
  code: string;
  label: string;
  reference: string;
  value: string;
}

export interface PayrollBase {
  label: string;
  value: string;
}

export interface PayrollPage {
  page: number;
  year: string;
  month: string;
  fields: PayrollField[];
  bases: PayrollBase[];
}

export interface PayrollValue {
  pages: PayrollPage[];
}

export type TranscriptionValue = CardValue | PayrollValue;

export interface TranscriptionResponse {
  id: string;
  tipo: DocumentType;
  status: TranscriptionStatus;
  erro: string | null;
  value: TranscriptionValue | null;
}

export interface CreatedTranscription {
  id: string;
}

export function isCardValue(value: TranscriptionValue): value is CardValue {
  return value.pages.every((page) => "days" in page);
}

export function isPayrollValue(value: TranscriptionValue): value is PayrollValue {
  return value.pages.every((page) => "fields" in page && "bases" in page);
}
