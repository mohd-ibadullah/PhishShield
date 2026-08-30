import { formatBenchmarkCaveat, formatBenchmarkFpr, formatBenchmarkMetric } from './metricFormatters';

type OfflineMetricPayload = { accuracy: number | null; precision: number | null; recall: number | null; f1_score: number | null; false_positive_rate: number | null };

function renderOfflineMetricPayload(payload: OfflineMetricPayload) {
  return {
    accuracy: formatBenchmarkMetric(payload.accuracy), precision: formatBenchmarkMetric(payload.precision),
    recall: formatBenchmarkMetric(payload.recall), f1_score: formatBenchmarkMetric(payload.f1_score),
    false_positive_rate: formatBenchmarkFpr(payload.false_positive_rate).valueText,
  };
}

function runTests() {
  console.log('Running metricFormatters unit tests...');

  // Mirrors the five visible dashboard metrics: null is absent, never zero.
  const nullPayload = renderOfflineMetricPayload({ accuracy: null, precision: null, recall: null, f1_score: null, false_positive_rate: null });
  console.log('All-null metric payload renders:', JSON.stringify(nullPayload));
  for (const [name, rendered] of Object.entries(nullPayload)) {
    if (rendered !== '—') throw new Error(`${name} null: expected '—', got '${rendered}'`);
  }

  // ── FPR (already had a guard pre-fix; this proves it) ──────────────────────

  // Case A: null FPR → "—" (was correct even before the UI fix)
  const nullFpr = formatBenchmarkFpr(null);
  console.log('Case A (null FPR):', JSON.stringify(nullFpr));
  if (nullFpr.valueText !== '—') {
    throw new Error(`FPR null: expected '—', got '${nullFpr.valueText}'`);
  }
  if (!nullFpr.captionText.includes('not computed')) {
    throw new Error(`FPR null caption: expected 'not computed', got '${nullFpr.captionText}'`);
  }
  if (nullFpr.valueText.includes('0.0')) {
    throw new Error(`FPR null: must NOT contain '0.0', got '${nullFpr.valueText}'`);
  }

  // Case B: real FPR value
  const realFpr = formatBenchmarkFpr(0.073);
  console.log('Case B (0.073 FPR):', JSON.stringify(realFpr));
  if (realFpr.valueText !== '7.3%') {
    throw new Error(`FPR 0.073: expected '7.3%', got '${realFpr.valueText}'`);
  }
  if (!realFpr.captionText.includes('lower is better')) {
    throw new Error(`FPR 0.073 caption: expected 'lower is better', got '${realFpr.captionText}'`);
  }

  // ── ACCURACY (sibling — was fabricating "0.0%" pre-fix) ───────────────────

  // Case C1: null accuracy → must be "—", not "0.0%"
  const nullAccuracy = formatBenchmarkMetric(null);
  console.log('Case C1 (null accuracy):', JSON.stringify(nullAccuracy));
  if (nullAccuracy !== '—') {
    throw new Error(`accuracy null: expected '—', got '${nullAccuracy}'`);
  }
  if (nullAccuracy === '0.0%') {
    throw new Error(`accuracy null: must NOT be fabricated '0.0%'`);
  }

  // Case C2: real accuracy value
  const realAccuracy = formatBenchmarkMetric(0.9719);
  console.log('Case C2 (0.9719 accuracy):', JSON.stringify(realAccuracy));
  if (realAccuracy !== '97.2%') {
    throw new Error(`accuracy 0.9719: expected '97.2%', got '${realAccuracy}'`);
  }

  // ── PRECISION (sibling — was fabricating "0.0%" pre-fix) ──────────────────

  // Case D1: null precision → must be "—"
  const nullPrecision = formatBenchmarkMetric(null);
  console.log('Case D1 (null precision):', JSON.stringify(nullPrecision));
  if (nullPrecision !== '—') {
    throw new Error(`precision null: expected '—', got '${nullPrecision}'`);
  }

  // Case D2: real precision value (0.940530... — exact training_meta value)
  const realPrecision = formatBenchmarkMetric(0.940530058177117);
  console.log('Case D2 (0.940530 precision):', JSON.stringify(realPrecision));
  if (realPrecision !== '94.1%') {
    throw new Error(`precision 0.940530: expected '94.1%', got '${realPrecision}'`);
  }

  // ── RECALL (sibling — was fabricating "0.0%" pre-fix) ─────────────────────

  // Case E1: null recall → must be "—"
  const nullRecall = formatBenchmarkMetric(null);
  console.log('Case E1 (null recall):', JSON.stringify(nullRecall));
  if (nullRecall !== '—') {
    throw new Error(`recall null: expected '—', got '${nullRecall}'`);
  }

  // Case E2: real recall value
  const realRecall = formatBenchmarkMetric(0.9911);
  console.log('Case E2 (0.9911 recall):', JSON.stringify(realRecall));
  if (realRecall !== '99.1%') {
    throw new Error(`recall 0.9911: expected '99.1%', got '${realRecall}'`);
  }

  // ── F1 SCORE (sibling — was fabricating "0.0%" pre-fix) ───────────────────

  // Case F1: null f1_score → must be "—"
  const nullF1 = formatBenchmarkMetric(null);
  console.log('Case F1 (null f1_score):', JSON.stringify(nullF1));
  if (nullF1 !== '—') {
    throw new Error(`f1_score null: expected '—', got '${nullF1}'`);
  }

  // Case F2: real f1 value
  const realF1 = formatBenchmarkMetric(0.9652);
  console.log('Case F2 (0.9652 f1_score):', JSON.stringify(realF1));
  if (realF1 !== '96.5%') {
    throw new Error(`f1_score 0.9652: expected '96.5%', got '${realF1}'`);
  }

  // ── BENCHMARK CAVEAT (computed by diagnostics/reproduce_headlines.py) ─────

  // Case G1: harness-computed counts with 0 shared families → caveat present,
  // matching the computed counts exactly.
  const caveatZeroShared = formatBenchmarkCaveat({ csv_records: 2000, template_families: 1115, families_shared_between_classes: 0 });
  console.log('Case G1 (0 shared families):', JSON.stringify(caveatZeroShared));
  const expectedG1 = 'measured on the committed 2000-row set: 1115 template families, 0 shared between classes → not a generalization measurement';
  if (caveatZeroShared !== expectedG1) {
    throw new Error(`caveat 0-shared: expected '${expectedG1}', got '${caveatZeroShared}'`);
  }

  // Case G2: different computed counts must change the string — a hardcoded
  // "0" (or any hardcoded count) fails here.
  const caveatShared = formatBenchmarkCaveat({ csv_records: 500, template_families: 87, families_shared_between_classes: 3 });
  console.log('Case G2 (3 shared families):', JSON.stringify(caveatShared));
  if (caveatShared === null || !caveatShared.includes('500-row set') || !caveatShared.includes('87 template families') || !caveatShared.includes('3 shared between classes')) {
    throw new Error(`caveat must reflect computed counts, got '${caveatShared}'`);
  }
  if (caveatShared.includes('0 shared between classes')) {
    throw new Error(`caveat hardcodes '0': got '${caveatShared}'`);
  }

  // Case G3: harness output unavailable → render nothing, never a fabricated caveat.
  const caveatMissing = formatBenchmarkCaveat(null);
  console.log('Case G3 (no harness output):', JSON.stringify(caveatMissing));
  if (caveatMissing !== null) {
    throw new Error(`caveat null input: expected null, got '${caveatMissing}'`);
  }

  console.log('All metricFormatters tests PASSED!');
}

runTests();
