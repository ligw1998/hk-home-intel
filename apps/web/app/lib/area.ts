export function sqftToSqm(value: number): number {
  return value * 0.092903;
}

export function formatAreaDual(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return "TBD";
  }
  const sqm = sqftToSqm(value);
  return `${value} sqft / ${sqm.toFixed(1)} sqm`;
}
