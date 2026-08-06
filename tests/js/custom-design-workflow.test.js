const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
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
  const page = loadPage('miniprogram/subpackages/design/pages/design-service/design-service.js');
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
  assert.equal(request.confirmation_proposal.preview_layout[0].preview_image_url, 'https://cdn.example.com/a.webp');
});

test('custom design confirmation opens a real-image review before creating an order', () => {
  const page = loadPage('miniprogram/subpackages/design/pages/design-service/design-service.js');
  const instance = {
    ...page,
    data: {
      ...page.data,
      request: page.decorateRequest({
        request_id: 'CD-CONFIRM',
        status: 'proposed',
        proposals: [{
          proposal_id: 'proposal-confirm',
          status: 'active',
          workbench: {
            layout: [{ id: 'a', selected_image_url: 'https://cdn.example.com/real-a.webp' }]
          }
        }]
      })
    },
    setData(patch) {
      Object.assign(this.data, patch);
    }
  };

  instance.confirmProposal();

  assert.equal(instance.data.confirmationOpen, true);
  assert.equal(
    instance.data.request.confirmation_proposal.preview_layout[0].preview_image_url,
    'https://cdn.example.com/real-a.webp'
  );
});

test('custom design list keeps every request and groups statuses for client filtering', () => {
  const page = loadPage('miniprogram/subpackages/design/pages/design-service-list/design-service-list.js');
  const requests = [
    page.decorateRequest({
      request_id: 'CD-WAITING',
      status: 'designing',
      updated_at: '2026-07-28T08:00:00Z',
      request: { wrist_size_cm: 16, bead_size_mm: 8, style_preference: '清透自然' },
      proposals: []
    }),
    page.decorateRequest({
      request_id: 'CD-PROPOSED',
      status: 'proposed',
      request: { wrist_size_cm: 15.5, bead_size_mm: 10, budget: '300–500 元' },
      proposals: [{
        proposal_id: 'proposal-list',
        status: 'active',
        title: '日常清透款',
        workbench: {
          layout: [
            { selected_image_url: 'https://cdn.example.com/a.webp' },
            { selected_image_url: 'https://cdn.example.com/b.webp' }
          ]
        }
      }]
    }),
    page.decorateRequest({
      request_id: 'CD-DONE',
      status: 'confirmed',
      proposals: []
    })
  ];
  const instance = {
    ...page,
    data: { ...page.data, requests, activeFilter: 'proposed' },
    setData(patch) {
      Object.assign(this.data, patch);
    }
  };

  instance.applyFilter();

  assert.equal(requests[0].filter_key, 'active');
  assert.equal(requests[1].filter_key, 'proposed');
  assert.equal(requests[1].bead_count, 2);
  assert.equal(requests[1].preview_materials.length, 2);
  assert.equal(requests[2].filter_key, 'finished');
  assert.deepEqual(instance.data.visibleRequests.map(item => item.request_id), ['CD-PROPOSED']);
});

test('manual design wrist selection shares the workspace wrist storage contract', () => {
  const page = loadPage('miniprogram/subpackages/design/pages/design-service/design-service.js');
  const storage = new Map();
  global.wx = {
    setStorageSync(key, value) {
      storage.set(key, value);
    }
  };
  const instance = {
    ...page,
    data: JSON.parse(JSON.stringify(page.data)),
    setData(patch) {
      Object.entries(patch).forEach(([key, value]) => {
        if (key === 'form.wrist_size_cm') this.data.form.wrist_size_cm = value;
        else this.data[key] = value;
      });
    }
  };

  instance.confirmWristPicker({ detail: { value: 17.3 } });

  assert.equal(instance.data.form.wrist_size_cm, '17.3');
  assert.equal(storage.get('workspaceWristSizeV1'), 17.3);
  assert.equal(storage.get('workspaceWristConfirmed'), true);
});

test('manual design collects explicit style, accessory, and scene preferences on the routed page', () => {
  const page = loadPage('miniprogram/subpackages/design/pages/design-service/design-service.js');
  const instance = {
    ...page,
    data: JSON.parse(JSON.stringify(page.data)),
    setData(patch) {
      Object.entries(patch).forEach(([key, value]) => {
        const formMatch = key.match(/^form\.(.+)$/);
        if (formMatch) this.data.form[formMatch[1]] = value;
        else this.data[key] = value;
      });
    }
  };

  assert.equal(instance.data.form.style_preference, '');
  assert.equal(instance.data.form.accessory_preference, '');
  assert.equal(instance.data.form.wear_scene, '');
  assert.match(instance.data.accessoryOptions.join('、'), /少量银饰/);
  assert.match(instance.data.wearSceneOptions.join('、'), /日常通勤/);
  instance.chooseOption({ currentTarget: { dataset: { field: 'accessory_preference', value: '少量银饰' } } });
  assert.equal(instance.data.form.accessory_preference, '少量银饰');

  const appJson = fs.readFileSync(path.resolve(__dirname, '../../miniprogram/app.json'), 'utf8');
  const pageJs = fs.readFileSync(path.resolve(__dirname, '../../miniprogram/subpackages/design/pages/design-service/design-service.js'), 'utf8');
  const pageWxml = fs.readFileSync(path.resolve(__dirname, '../../miniprogram/subpackages/design/pages/design-service/design-service.wxml'), 'utf8');
  assert.match(appJson, /"pages\/design-service\/design-service"/);
  assert.match(pageJs, /!form\.style_preference \|\| !form\.accessory_preference \|\| !form\.wear_scene/);
  assert.match(pageJs, /preference_confirmed: true/);
  assert.match(pageWxml, /wx:for="\{\{accessoryOptions\}\}"/);
  assert.match(pageWxml, /wx:for="\{\{wearSceneOptions\}\}"/);
  assert.match(pageWxml, /提交并支付设计保证金9\.9元/);
});

test('manual design keeps the 9.9-yuan deposit button on one line', () => {
  const pageWxss = fs.readFileSync(path.resolve(__dirname, '../../miniprogram/subpackages/design/pages/design-service/design-service.wxss'), 'utf8');
  assert.match(pageWxss, /\.submit\{[^}]*min-width:0;[^}]*padding:0 28rpx;[^}]*white-space:nowrap;[^}]*font-size:27rpx;[^}]*line-height:1;/);
});

test('manual design keeps the focused color preference input above the keyboard', () => {
  const page = loadPage('miniprogram/subpackages/design/pages/design-service/design-service.js');
  const scrolls = [];
  global.wx = {
    getWindowInfo() {
      return { windowHeight: 844 };
    },
    pageScrollTo(options) {
      scrolls.push(options);
    },
    createSelectorQuery() {
      const query = {
        in() {
          return query;
        },
        select(selector) {
          assert.equal(selector, '#designColorPreferenceField');
          return {
            boundingClientRect() {
              return query;
            }
          };
        },
        selectViewport() {
          return {
            scrollOffset() {
              return query;
            }
          };
        },
        exec(callback) {
          callback([{ bottom: 680 }, { scrollTop: 120 }]);
        }
      };
      return query;
    }
  };
  const instance = {
    ...page,
    focusedFieldSelector: '#designColorPreferenceField',
    keyboardHeight: 320
  };

  instance.scrollFocusedFieldIntoView();

  assert.deepEqual(scrolls, [{ scrollTop: 300, duration: 180 }]);
  const pageWxml = fs.readFileSync(path.resolve(__dirname, '../../miniprogram/subpackages/design/pages/design-service/design-service.wxml'), 'utf8');
  const pageWxss = fs.readFileSync(path.resolve(__dirname, '../../miniprogram/subpackages/design/pages/design-service/design-service.wxss'), 'utf8');
  assert.match(pageWxml, /id="designColorPreferenceInput"/);
  assert.match(pageWxml, /id="designColorPreferenceField"/);
  assert.match(pageWxml, /<textarea[\s\S]*?class="note-input color-preference-input"/);
  assert.match(pageWxml, /adjust-position="\{\{true\}\}"/);
  assert.match(pageWxml, /cursor-spacing="160"/);
  assert.match(pageWxml, /bindkeyboardheightchange="onFieldKeyboardHeightChange"/);
  assert.match(pageWxml, /placeholder-style="color: #aaa49a; font-size: 27rpx; font-weight: 400;"/);
  assert.match(pageWxml, /class="note-input"/);
  assert.match(pageWxml, /class="revision-input"/);
  assert.match(pageWxml, /class="confirm-material-image"/);
  assert.match(pageWxss, /\.note-input\{[\s\S]*?height:132rpx;/);
  assert.match(pageWxss, /\.field-input-placeholder\{color:#aaa49a;font-weight:400;opacity:1\}/);
  assert.doesNotMatch(pageWxss, /\.note-input\{[^}]*-webkit-text-fill-color/);
  assert.doesNotMatch(pageWxss, /\.field-color-preference|\.field-optional|\.field \.color-preference-input|\.color-preference-placeholder/);
  assert.doesNotMatch(pageWxss, /\.(?:field|revision-card|confirm-material)\s+(?:input|textarea|image|text)\b/);
});

test('manual design preserves the initial keyboard height and retries the focused field check', async t => {
  const page = loadPage('miniprogram/subpackages/design/pages/design-service/design-service.js');
  let checks = 0;
  const instance = {
    ...page,
    scrollFocusedFieldIntoView() {
      checks += 1;
    }
  };
  t.after(() => instance.onUnload());

  instance.onColorPreferenceFocus({ detail: { height: 318 } });
  await new Promise(resolve => setTimeout(resolve, 20));

  assert.equal(instance.focusedFieldSelector, '#designColorPreferenceField');
  assert.equal(instance.keyboardHeight, 318);
  assert.equal(checks, 1);
  assert.equal(instance.focusedFieldScrollTimers.length, 2);
});

test('opening a designer proposal stores a complete exact workspace import intent', () => {
  const page = loadPage('miniprogram/subpackages/design/pages/design-service/design-service.js');
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
  assert.equal(payload.bracelet_plan.validation.is_valid, false);
  assert.equal(payload.bracelet_plan.validation.fit_status, 'unverifiable');
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
