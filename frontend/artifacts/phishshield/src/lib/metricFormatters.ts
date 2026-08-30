/**
 * Formatting utilities for benchmark and offline evaluation metrics.
 */

export function formatBenchmarkFpr(fpr: number | null | undefined): { valueText: string; captionText: string } {
  if (fpr === null || fpr === undefined || Number.isNaN(fpr)) {
    return { valueText: '—', captionText: '(not computed)' };
  }
  return { valueText: `${(fpr * 100).toFixed(1)}%`, captionText: '(lower is better)' };
}

export function formatBenchmarkMetric(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—';
  }
  return `${(value * 100).toFixed(1)}%`;
}
