function normalizeBeadSizes(itemsOrSizes = []) {
  return (itemsOrSizes || [])
    .map(item => Number(
      typeof item === 'number'
        ? item
        : (item && (item.string_axis_width_mm || item.size || item.diameter || item.size_mm))
    ))
    .filter(size => Number.isFinite(size) && size > 0);
}

function estimateInnerCircumferenceMm(itemsOrSizes = []) {
  const sizes = normalizeBeadSizes(itemsOrSizes);
  if (sizes.length < 3) return 0;

  const radii = sizes.map(size => size / 2);
  const contacts = radii.map((radius, index) => radius + radii[(index + 1) % radii.length]);
  const centralAngles = centerRadius => contacts.map(contact => (
    2 * Math.asin(Math.min(1, contact / (2 * centerRadius)))
  ));
  let lower = Math.max(Math.max(...radii), Math.max(...contacts) / 2) * (1 + 1e-9);
  if (centralAngles(lower).reduce((sum, angle) => sum + angle, 0) < Math.PI * 2) return 0;

  let upper = Math.max(lower * 2, contacts.reduce((sum, contact) => sum + contact, 0));
  while (centralAngles(upper).reduce((sum, angle) => sum + angle, 0) > Math.PI * 2) {
    upper *= 2;
  }
  for (let iteration = 0; iteration < 64; iteration += 1) {
    const midpoint = (lower + upper) / 2;
    const angleSum = centralAngles(midpoint).reduce((sum, angle) => sum + angle, 0);
    if (angleSum > Math.PI * 2) lower = midpoint;
    else upper = midpoint;
  }

  const centerRadius = (lower + upper) / 2;
  const angles = centralAngles(centerRadius);
  return radii.reduce((sum, radius, index) => {
    const previousAngle = angles[(index - 1 + angles.length) % angles.length];
    const beadAngle = (previousAngle + angles[index]) / 2;
    return sum + Math.max(0, centerRadius - radius) * beadAngle;
  }, 0);
}

function recommendBeadCount(itemsOrSizes = [], wristSizeCm = 16, options = {}) {
  const sizes = normalizeBeadSizes(itemsOrSizes);
  const averageSize = sizes.length
    ? sizes.reduce((sum, size) => sum + size, 0) / sizes.length
    : Number(options.defaultBeadSizeMm || 8);
  const allowanceMm = Number(options.allowanceMm || 0);
  const minCount = Math.max(3, Number(options.minCount || 3));
  const maxCount = Math.max(minCount, Number(options.maxCount || minCount));
  const targetMm = Math.max(0, Number(wristSizeCm || 0) * 10 + allowanceMm);
  let best = { count: minCount, difference: Number.POSITIVE_INFINITY, isShort: true };

  for (let count = minCount; count <= maxCount; count += 1) {
    const innerLength = estimateInnerCircumferenceMm(Array(count).fill(averageSize));
    const difference = Math.abs(innerLength - targetMm);
    const isShort = innerLength < targetMm;
    if (
      difference < best.difference - 1e-6
      || (Math.abs(difference - best.difference) <= 1e-6 && best.isShort && !isShort)
    ) {
      best = { count, difference, isShort };
    }
  }
  return best.count;
}

function expandSequenceToCount(sequence = [], targetCount = 0) {
  const source = Array.isArray(sequence) ? sequence.filter(Boolean) : [];
  if (!source.length) return [];
  const count = Math.max(source.length, Math.floor(Number(targetCount) || 0));
  if (count === source.length) return source.slice();

  const expanded = [];
  source.forEach((item, index) => {
    const start = Math.round(index * count / source.length);
    const end = Math.round((index + 1) * count / source.length);
    const copies = Math.max(1, end - start);
    for (let copy = 0; copy < copies; copy += 1) expanded.push(item);
  });
  return expanded.slice(0, count);
}

module.exports = {
  expandSequenceToCount,
  estimateInnerCircumferenceMm,
  normalizeBeadSizes,
  recommendBeadCount
};
