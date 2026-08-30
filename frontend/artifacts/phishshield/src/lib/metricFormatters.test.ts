import { formatBenchmarkFpr, formatBenchmarkMetric } from './metricFormatters';

function runTests() {
  console.log('Running metricFormatters unit tests...');

  // Test Case A: Backend returns null false_positive_rate (missing confusion matrix)
  const nullResult = formatBenchmarkFpr(null);
  console.log('Case A (null FPR):', JSON.stringify(nullResult));
  if (nullResult.valueText !== '—') {
    throw new Error(`Expected valueText to be '—', got '${nullResult.valueText}'`);
  }
  if (!nullResult.captionText.includes('not computed')) {
    throw new Error(`Expected captionText to include 'not computed', got '${nullResult.captionText}'`);
  }
  if (nullResult.valueText.includes('0.0')) {
    throw new Error(`Expected valueText NOT to contain '0.0', got '${nullResult.valueText}'`);
  }

  // Test Case B: Backend returns real FPR (e.g. 0.073)
  const realResult = formatBenchmarkFpr(0.073);
  console.log('Case B (0.073 FPR):', JSON.stringify(realResult));
  if (realResult.valueText !== '7.3%') {
    throw new Error(`Expected valueText to be '7.3%', got '${realResult.valueText}'`);
  }
  if (!realResult.captionText.includes('lower is better')) {
    throw new Error(`Expected captionText to include 'lower is better', got '${realResult.captionText}'`);
  }

  // Test Case C: General metric formatting (Accuracy/Precision/Recall/F1)
  if (formatBenchmarkMetric(null) !== '—') {
    throw new Error(`Expected formatBenchmarkMetric(null) to be '—', got '${formatBenchmarkMetric(null)}'`);
  }
  if (formatBenchmarkMetric(0.952) !== '95.2%') {
    throw new Error(`Expected formatBenchmarkMetric(0.952) to be '95.2%', got '${formatBenchmarkMetric(0.952)}'`);
  }

  console.log('All metricFormatters tests PASSED!');
}

runTests();
