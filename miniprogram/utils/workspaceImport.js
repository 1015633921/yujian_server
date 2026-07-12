function cleanName(value = '') {
  return String(value || '').trim();
}

function buildFreshWorkspaceDraft(options = {}) {
  const name = cleanName(options.name) || cleanName(options.fallbackName);
  const wristSize = Number(options.wristSize);
  const now = Date.now();
  return {
    designId: '',
    design_id: '',
    name,
    title: name,
    userId: '',
    selected: Array.isArray(options.selected) ? options.selected.slice() : [],
    placements: Array.isArray(options.placements)
      ? options.placements.map(item => ({ ...(item || {}) }))
      : [],
    attachedPendants: [],
    wristSize: Number.isFinite(wristSize) && wristSize > 0 ? wristSize : 16,
    wearStyle: 'single',
    isLooseMode: false,
    sourceContext: options.sourceContext ? { ...options.sourceContext } : null,
    createdAt: now,
    updatedAt: now,
    summary: {}
  };
}

module.exports = {
  buildFreshWorkspaceDraft
};
