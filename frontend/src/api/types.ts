// API integer tokens become bigint before JSON can round them.
export interface Balance {
  balance_minor: bigint;
  currency: 'COP';
}
export interface Account extends Balance {
  id: string;
  handle: string;
  display_name: string;
}
export interface Movement {
  operation_id: string;
  operation_type: 'deposit' | 'transfer';
  amount_minor: bigint;
  currency: 'COP';
  created_at: string;
  counterparty_handle: string;
  shared_expense_id: string | null;
  shared_expense_title: string | null;
}
export interface Participant {
  account_id: string;
  handle: string;
  display_name: string;
  share_minor: bigint;
  paid_minor: bigint;
  outstanding_minor: bigint;
  excess_minor: bigint;
  settled: boolean;
}
export interface SharedExpense {
  id: string;
  title: string;
  total_minor: bigint;
  currency: 'COP';
  payer: string;
  participants: Participant[];
  outstanding_total_minor: bigint;
  settled: boolean;
}
export interface TransferInput {
  source_account_id: string;
  destination_account_id: string;
  amount_minor: bigint;
  currency: 'COP';
  shared_expense_id: string | null;
  idempotency_key: string;
}
export interface TransferResult {
  operation_id: string;
  source_balance_minor: bigint;
  destination_balance_minor: bigint;
  currency: 'COP';
  shared_expense_id: string | null;
  replayed: boolean;
}
export interface ExpenseInput {
  title: string;
  total_minor: bigint;
  currency: 'COP';
  payer_account_id: string;
  participant_account_ids: string[];
  split: 'equal';
}
export interface CreditProfile {
  monthly_savings_minor: bigint;
  months_consistent: number;
  compliance_ratio: number | null;
  down_payment_minor: bigint;
  currency: 'COP';
}
export interface CreditSummary extends CreditProfile {
  has_enough_evidence: boolean;
}
export interface Waypoint {
  capacity: number;
  stability: number;
  qualify_probability: number;
  monthly_savings_minor: bigint;
  months_consistent: number;
}
export interface CreditStep {
  order: number;
  action: string;
  magnitude: string;
}
export interface CreditPath {
  profile: CreditProfile;
  has_enough_evidence: boolean;
  headline: string;
  /** Perfiles reales del dataset: [capacidad, estabilidad, P(califica)]. */
  population: [number, number, number][];
  /** Perfiles que el modelo generó, superpuestos a los reales. */
  generated: [number, number, number][];
  trajectory: Waypoint[];
  steps: CreditStep[];
}
