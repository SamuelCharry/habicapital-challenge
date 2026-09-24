import type {
  Account,
  Balance,
  ExpenseInput,
  Movement,
  SharedExpense,
  TransferInput,
  TransferResult,
} from './types';

const baseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

export function decodeResponse(text: string): unknown {
  // Protect integer tokens BEFORE JSON.parse; strings are consumed first.
  const exact = text.replace(/"(?:\\.|[^"\\])*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g, token =>
    /^-?\d+$/.test(token) ? `"${token}"` : token,
  );
  return JSON.parse(exact, (key, value: unknown) => {
    if (!key.endsWith('_minor')) return value;
    if (typeof value !== 'string' || !/^-?\d+$/.test(value))
      throw new Error('El servidor devolvió un importe inválido.');
    return BigInt(value);
  });
}

export function encodeRequest(body: unknown): string {
  // Monetary input fields must reach the strict backend as JSON integers.
  return JSON.stringify(body, (_key, value: unknown) =>
    typeof value === 'bigint' ? value.toString() : value,
  ).replace(/("(?:amount_minor|total_minor)":)"(-?\d+)"/g, '$1$2');
}

function serverMessage(value: unknown): string {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(serverMessage).join(' ');
  if (value && typeof value === 'object')
    return Object.entries(value)
      .map(([key, message]) => `${key === 'detail' ? '' : `${key}: `}${serverMessage(message)}`)
      .join(' ');
  return '';
}

async function request<T>(path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${baseUrl}/api${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: {
        Accept: 'application/json',
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      body: body === undefined ? undefined : encodeRequest(body),
      signal: AbortSignal.timeout(15000),
    });
  } catch {
    throw new Error('No pudimos confirmar la respuesta. Revisa tu conexión y vuelve a intentar.');
  }
  let text: string;
  try {
    text = await response.text();
  } catch {
    throw new Error('No pudimos confirmar la respuesta. Revisa tu conexión y vuelve a intentar.');
  }
  let data: unknown;
  // Validation errors can have monetary field names with arrays of messages.
  // They are error descriptions, not monetary response values.
  try {
    data = response.ok ? decodeResponse(text) : JSON.parse(text);
  } catch {
    throw new Error(`No pudimos leer la respuesta del servidor (${response.status}). Vuelve a intentar.`);
  }
  if (!response.ok)
    throw new Error(serverMessage(data) || `El servidor respondió con un error (${response.status}).`);
  return data as T;
}

export const api = {
  accounts: () => request<Account[]>('/accounts/'),
  account: (id: string) => request<Account>(`/accounts/${id}/`),
  createAccount: (handle: string, display_name: string) =>
    request<Account>('/accounts/', { handle, display_name }),
  balance: (id: string) => request<Balance>(`/accounts/${id}/balance/`),
  deposit: (id: string, amount_minor: bigint) =>
    request<Balance & { operation_id: string }>(`/accounts/${id}/deposits/`, {
      amount_minor,
      currency: 'COP',
    }),
  history: async (id: string) =>
    (await request<Movement[]>(`/accounts/${id}/history/`)).sort((a, b) =>
      b.created_at.localeCompare(a.created_at),
    ),
  expenses: (id: string) => request<SharedExpense[]>(`/accounts/${id}/shared-expenses/`),
  expense: (id: string) => request<SharedExpense>(`/shared-expenses/${id}/`),
  createExpense: (body: ExpenseInput) => request<SharedExpense>('/shared-expenses/', body),
  transfer: (body: TransferInput) => request<TransferResult>('/transfers/', body),
};
