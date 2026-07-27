const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

function loadPage(relativePath) {
  const absolutePath = path.resolve(__dirname, '../..', relativePath);
  delete require.cache[require.resolve(absolutePath)];
  let pageConfig = null;
  global.Page = config => {
    pageConfig = config;
  };
  require(absolutePath);
  return pageConfig;
}

test('custom design proposal is decorated with a deterministic ring preview', () => {
  const page = loadPage('miniprogram/pages/design-service/design-service.js');
  const request = page.decorateRequest({
    request_id: 'CD-1',
    status: 'proposed',
    proposals: [{
      proposal_id: 'proposal-1',
      status: 'active',
      image_urls: [],
      workbench: {
        summary: { price: '26.00' },
        layout: [
          { id: 'a', selected_image_url: 'https://cdn.example.com/a.webp' },
          { id: 'b', selected_image_url: 'https://cdn.example.com/b.webp' },
          { id: 'c', selected_image_url: 'https://cdn.example.com/c.webp' }
        ]
      }
    }]
  });

  assert.equal(request.has_structured_proposal, true);
  assert.equal(request.latest_proposal.bead_count, 3);
  assert.equal(request.latest_proposal.price_text, '26.00');
  assert.equal(request.latest_proposal.preview_layout.length, 3);
  assert.equal(
    new Set(request.latest_proposal.preview_layout.map(item => item.preview_key)).size,
    3
  );
});

test('opening a designer proposal stores a complete exact workspace import intent', () => {
  const page = loadPage('miniprogram/pages/design-service/design-service.js');
  const storage = new Map();
  let switchedTo = '';
  global.wx = {
    setStorageSync(key, value) {
      storage.set(key, value);
    },
    removeStorageSync(key) {
      storage.delete(key);
    },
    switchTab({ url }) {
      switchedTo = url;
    },
    showToast() {}
  };
  const instance = {
    ...page,
    data: {
      ...page.data,
      request: page.decorateRequest({
        request_id: 'CD-2',
        status: 'proposed',
        proposals: [{
          proposal_id: 'proposal-2',
          title: '设计师专属款',
          status: 'active',
          workbench: {
            wrist_size_cm: 16,
            bead_size_mm: 8,
            layout: [{
              id: 'bead-a',
              material_id: 'bead-a',
              selected_image_url: 'https://cdn.example.com/exact-a.webp'
            }]
          }
        }]
      })
    }
  };

  instance.openProposalInWorkspace();

  const payload = storage.get('diyWorkbenchPayload');
  assert.equal(storage.get('workspacePreset'), 'backend-recommended');
  assert.equal(payload.source, 'custom_design');
  assert.equal(payload.bracelet_plan.validation.is_valid, true);
  assert.equal(
    payload.bracelet_plan.layout[0].image_url,
    'https://cdn.example.com/exact-a.webp'
  );
  assert.equal(switchedTo, '/pages/workspace/workspace');
});

test('workspace trusts a designer layout below recommendation minimum and keeps exact images', () => {
  const page = loadPage('miniprogram/pages/workspace/workspace.js');
  const layout = ['a', 'b', 'c'].map(id => ({
    material_id: id,
    selected_image_url: `https://cdn.example.com/${id}-exact.webp`
  }));
  const payload = {
    source: 'custom_design',
    source_context: { source: 'custom_design', title: '设计师方案' },
    wrist_size_cm: 16,
    bracelet_plan: {
      title: '设计师方案',
      validation: { is_valid: true },
      layout
    }
  };
  let placementInput = null;
  let importedDraft = null;
  const instance = Object.assign({}, page, {
    data: { ...page.data, wristSize: 16 },
    materialPayloadReady: true,
    buildBackendRecommendationSelected: () => ['a', 'b', 'c'],
    findMaterialById: id => ({
      id,
      top: 'bead',
      size: 8,
      price: 10,
      stock: 99,
      enabled: true
    }),
    resetWorkspaceRuntime() {},
    normalizePlacements(selected, placements) {
      placementInput = placements;
      return placements;
    },
    rebuildRingPlacementsForVisualSlots(selected, placements) {
      return placements;
    },
    replaceCurrentDesignWithImportedDraft(options) {
      importedDraft = options;
    },
    setData(patch) {
      Object.assign(this.data, patch);
    },
    recalculate() {}
  });
  global.wx = {
    getStorageSync(key) {
      return key === 'diyWorkbenchPayload' ? payload : '';
    },
    setStorageSync() {},
    showToast() {}
  };

  const applied = instance.applyBackendRecommendation({ silent: true });

  assert.equal(applied, true);
  assert.equal(importedDraft.selected.length, 3);
  assert.deepEqual(
    placementInput.map(item => item.image_url),
    layout.map(item => item.selected_image_url)
  );
});
