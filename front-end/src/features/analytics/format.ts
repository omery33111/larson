
// ------------------------- NUMBER FORMATTING -------------------------
//
// Mirrors back-end/analytics/formatting.py. Every number the user reads carries its unit,
// on both sides of the wire: a bare "10.35" in a sentence could be dollars, a percentage or
// points, and the reader should never have to guess which.

const CURRENCY_SYMBOLS: { [code: string]: string } = {
  USD: '$',
  EUR: '€',
  GBP: '£',
  ILS: '₪',
  JPY: '¥',
};


export const money = (value: number | null | undefined, currency: string = 'USD') => {
  if (value === null || value === undefined) return '—';

  const symbol = CURRENCY_SYMBOLS[(currency || 'USD').toUpperCase()];
  const amount = Math.abs(value);
  const text = amount.toLocaleString('en-US', {
    minimumFractionDigits: Number.isInteger(amount) ? 0 : 2,
    maximumFractionDigits: 2,
  });
  const sign = value < 0 ? '-' : '';

  return symbol ? `${sign}${symbol}${text}` : `${sign}${text} ${(currency || '').toUpperCase()}`.trim();
};


export const percent = (value: number | null | undefined) =>
  value === null || value === undefined ? '—' : `${Number(value.toFixed(2))}%`;


/** A pure ratio - profit factor, win/loss, recovery factor. Carries no unit by nature. */
export const ratio = (value: number | null | undefined) =>
  value === null || value === undefined ? '—' : `${Number(value.toFixed(2))}`;


export const points = (value: number | null | undefined) =>
  value === null || value === undefined ? '—' : `${Number(value.toFixed(2))} נק'`;


export const tradeCount = (count: number) => (count === 1 ? 'עסקה אחת' : `${count} עסקאות`);
