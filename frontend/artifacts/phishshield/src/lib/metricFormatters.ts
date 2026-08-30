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

export interface BenchmarkCaveatCounts {
  csv_records: number;
  template_families: number;
  families_shared_between_classes: number;
}

/**
 * Render the committed-dataset caveat from counts computed by
 * diagnostics/reproduce_headlines.py. Returns null when the harness output
 * is unavailable — the caller renders nothing rather than a fabricated caveat.
 */
export function formatBenchmarkCaveat(counts: BenchmarkCaveatCounts | null | undefined): string | null {
  if (!counts) {
    return null;
  }
  return `measured on the committed ${counts.csv_records}-row set: ${counts.template_families} template families, ${counts.families_shared_between_classes} shared between classes → not a generalization measurement`;
}
