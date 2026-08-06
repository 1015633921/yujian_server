const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'miniprogram/pages/workspace/workspace.js'), 'utf8');

function loadWorkspacePage() {
  const workspacePath = path.join(root, 'miniprogram/pages/workspace/workspace.js');
  delete require.cache[require.resolve(workspacePath)];
  let pageConfig = null;
  global.Page = config => {
    pageConfig = config;
  };
  require(workspacePath);
  return pageConfig;
}

test('workspace bypasses stored material caches during a background refresh', () => {
  assert.match(source, /workspaceMaterialCatalogV9/);
  assert.match(source, /refreshMaterialCatalogInBackground\(\)/);
  assert.match(source, /force: true,[\s\S]*background: true/);
  assert.match(source, /!options\.force && materialCache\[cacheKey\]/);
  assert.match(source, /onShow\(\)[\s\S]*this\.workspaceHasShown[\s\S]*this\.refreshMaterialCatalogInBackground\(\)/);
  assert.doesNotMatch(source, /materialCatalogRefreshTimer|MATERIAL_VISIBLE_REFRESH_INTERVAL/);
});

test('workspace evicts decoded images and textures when the material version changes', () => {
  assert.match(source, /applyMaterialPayloadVersion\(data = \{\}\)/);
  assert.match(source, /this\.canvasImageCache = \{\}/);
  assert.match(source, /this\.canvasTextureCache = \{\}/);
  assert.match(source, /this\.materialImagePreloadSet = \{\}/);
  assert.match(source, /refreshSelectedMaterialDetails\(\)/);
  assert.match(source, /fetchMaterialsByIds\(ids, \{ force: true \}\)/);
});

test('workspace treats measured geometry as a material dependency', () => {
  assert.match(source, /materialPagePayloadSignature\(payload = \{\}\)[\s\S]*physical\.stringAxisWidthMm/);
  assert.match(source, /selectedMaterialDependencySignature[\s\S]*physical\.bodyWidthMm[\s\S]*physical\.bodyHeightMm/);
  assert.match(source, /string_axis_width_mm: material\.string_axis_width_mm \|\| 0/);
  assert.match(source, /beadSize: this\.getMaterialDisplaySize\(id\)/);
});

test('physical-only edits invalidate page and selected-material signatures', () => {
  const page = loadWorkspacePage();
  const before = {
    id: 'triangle-20',
    top: 'accessory',
    size: 20,
    material_params: {
      bead_shape: 'triangle',
      placement_mode: 'threaded',
      string_axis_width_mm: 20,
      body_width_mm: 20,
      body_height_mm: 19
    }
  };
  const after = {
    ...before,
    material_params: {
      ...before.material_params,
      string_axis_width_mm: 13,
      body_width_mm: 13,
      body_height_mm: 13
    }
  };

  const beforePageSignature = page.materialPagePayloadSignature({ version: 'same', materials: [before] });
  const afterPageSignature = page.materialPagePayloadSignature({ version: 'same', materials: [after] });
  assert.notEqual(beforePageSignature, afterPageSignature);

  const instance = Object.assign({}, page, {
    data: { ...page.data, selected: [before.id] },
    materialCatalog: [before]
  });
  instance.rebuildMaterialLookup(instance.materialCatalog, { resetDesignCaches: false });
  const beforeSelectedSignature = instance.selectedMaterialDependencySignature();
  instance.materialCatalog = [after];
  instance.rebuildMaterialLookup(instance.materialCatalog, { resetDesignCaches: false });
  const afterSelectedSignature = instance.selectedMaterialDependencySignature();
  assert.notEqual(beforeSelectedSignature, afterSelectedSignature);
});

test('workspace uses the gallery as-is and never filters it by the primary image', () => {
  const page = loadWorkspacePage();
  const instance = Object.assign({}, page, {
    normalizeImageUrlIdentity(value) {
      return String(value || '').split('?')[0];
    }
  });
  const primary = 'https://cdn.example.com/main.webp';
  const gallery = [primary, 'https://cdn.example.com/side.webp'];

  assert.deepEqual(instance.materialOwnImageUrls({
    top: 'accessory',
    image_url: primary,
    image_urls: gallery
  }), gallery);
});

test('workspace keeps its entry mask until the initial bracelet images are ready', async () => {
  const page = loadWorkspacePage();
  const imageCache = {};
  const instance = Object.assign({}, page, {
    data: {
      ...page.data,
      workspaceLoading: true,
      selected: ['bead-a'],
      placements: [{ image_url: 'https://cdn.example.com/bracelet.webp' }],
      visibleMaterials: [{ image_url: 'https://cdn.example.com/card.webp' }]
    },
    workspaceReadyFlags: { layout: true, canvas: true, materials: true, images: false },
    canvasImageCache: imageCache,
    getCachedSelectedMaterials() {
      return [{ image_url: 'https://cdn.example.com/bracelet.webp' }];
    },
    getCanvasImage(url) {
      imageCache[url] = { loading: true, waiters: [] };
      return null;
    },
    preloadWorkspaceNativeImage() {
      return Promise.resolve();
    },
    markWorkspaceReady(flag) {
      this.workspaceReadyFlags[flag] = true;
      if (flag === 'images') clearTimeout(this.workspaceLoadingFallbackTimer);
    }
  });

  instance.maybePreloadWorkspaceEntryImages();
  assert.equal(instance.workspaceEntryImagePreloadStarted, true);
  assert.equal(imageCache['https://cdn.example.com/bracelet.webp'].waiters.length, 1);
  imageCache['https://cdn.example.com/bracelet.webp'].waiters[0]();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(instance.workspaceReadyFlags.images, true);
});

test('workspace does not reveal a pending recommendation before its images can be queued', () => {
  const page = loadWorkspacePage();
  const instance = Object.assign({}, page, {
    data: { ...page.data, workspaceLoading: true },
    workspaceReadyFlags: { layout: true, canvas: true, materials: true, images: false },
    pendingBackendRecommendation: true
  });
  instance.maybePreloadWorkspaceEntryImages();
  assert.equal(instance.workspaceEntryImagePreloadStarted, undefined);
});
