function oneDecimal(value) {
  if (value === null || value === undefined || value === '') return '';
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric.toFixed(1) : '';
}

function effectiveWristText(summary = {}, allowanceCm = 0.8) {
  const explicit = oneDecimal(summary.currentWrist);
  if (explicit) return explicit;
  const length = Number(summary.length);
  if (!Number.isFinite(length)) return '--';
  return Math.max(0, length - Number(allowanceCm || 0)).toFixed(1);
}

module.exports = {
  effectiveWristText
};
