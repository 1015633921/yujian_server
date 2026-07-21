const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const script = fs.readFileSync(path.join(root, 'static/admin/admin.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'static/admin/index.html'), 'utf8');

function adminRuntime(elements = {}) {
  const context = {
    window: { location: { pathname: '/admin' } },
    localStorage: { getItem: () => '' },
    document: { getElementById: (id) => elements[id] || null },
    console,
    URLSearchParams,
    setTimeout,
    clearTimeout,
  };
  vm.createContext(context);
  vm.runInContext(script, context);
  vm.runInContext(`
    state.cache.materialTypes = [
      { code: 'bead', name: '珠子', enabled: true, sort_order: 10 },
      { code: 'accessory', name: '配饰', enabled: true, sort_order: 20 }
    ];
    state.cache.materialTaxonomy = [
      { id: 'cat-bead', kind: 'category', top: 'bead', name: '幽灵水晶', enabled: true, series: [] },
      { id: 'cat-accessory', kind: 'category', top: 'accessory', name: '幽灵随形', enabled: true, series: [] }
    ];
  `, context);
  return context;
}

test('new variety form preselects the category type and only lists matching categories', () => {
  const classList = { remove() {} };
  const elements = {
    drawerEyebrow: { textContent: '' },
    drawerTitle: { textContent: '' },
    drawerBody: { innerHTML: '' },
    drawerMask: { classList },
    drawer: { classList, scrollTop: 0 },
  };
  const runtime = adminRuntime(elements);

  runtime.renderMaterialVarietyForm({ enabled: true }, 'cat-accessory');

  assert.match(elements.drawerBody.innerHTML, /id="catalog_variety_top"/);
  assert.match(elements.drawerBody.innerHTML, /value="accessory" selected/);
  assert.match(elements.drawerBody.innerHTML, /value="cat-accessory" selected/);
  assert.doesNotMatch(elements.drawerBody.innerHTML, /value="cat-bead"/);
});

test('changing the variety type replaces category options and clears mismatched selection', () => {
  const elements = {
    catalog_variety_top: { value: 'accessory' },
    catalog_variety_category: { value: 'cat-bead', innerHTML: '' },
  };
  const runtime = adminRuntime(elements);

  runtime.updateCatalogVarietyCategoryOptions();

  assert.equal(elements.catalog_variety_category.value, '');
  assert.match(elements.catalog_variety_category.innerHTML, /value="cat-accessory"/);
  assert.doesNotMatch(elements.catalog_variety_category.innerHTML, /value="cat-bead"/);
});

test('SKU search waits for Chinese IME composition to finish', () => {
  const runtime = adminRuntime();

  runtime.handleMaterialKeywordCompositionStart();
  runtime.handleMaterialKeywordInput({ isComposing: true });

  assert.equal(vm.runInContext('state.materialUi.composing', runtime), true);
  assert.equal(vm.runInContext('Boolean(timers.materials)', runtime), false);

  runtime.handleMaterialKeywordCompositionEnd();

  assert.equal(vm.runInContext('state.materialUi.composing', runtime), false);
  assert.equal(vm.runInContext('Boolean(timers.materials)', runtime), true);
  vm.runInContext('clearTimeout(timers.materials); delete timers.materials', runtime);
  assert.match(html, /oncompositionstart="handleMaterialKeywordCompositionStart\(\)"/);
  assert.match(html, /oncompositionend="handleMaterialKeywordCompositionEnd\(\)"/);
});

test('SKU search ignores an older response that arrives after the latest query', async () => {
  const elements = Object.fromEntries([
    'materialKeyword', 'materialTop', 'materialCategory', 'materialElement', 'materialStatus',
    'materialStockState', 'materialMargin', 'materialQuality', 'materialSpecState'
  ].map(id => [id, { value: '' }]));
  const runtime = adminRuntime(elements);
  const requests = [];
  const renders = [];
  runtime.ensureMaterialAdminMeta = async () => {};
  runtime.api = path => new Promise(resolve => requests.push({ path, resolve }));
  runtime.renderMaterialsTable = () => renders.push(vm.runInContext('state.cache.materialSpus[0]?.key || ""', runtime));

  const older = runtime.loadMaterials();
  await new Promise(resolve => setImmediate(resolve));
  elements.materialKeyword.value = '幽灵';
  const latest = runtime.loadMaterials();
  await new Promise(resolve => setImmediate(resolve));

  assert.equal(requests.length, 2);
  requests[1].resolve({
    items: [{ key: 'latest', items: [] }],
    pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 }
  });
  await latest;
  requests[0].resolve({
    items: [{ key: 'older', items: [] }],
    pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 }
  });
  await older;

  assert.match(requests[1].path, /keyword=%E5%B9%BD%E7%81%B5/);
  assert.deepEqual(renders, ['latest']);
  assert.equal(vm.runInContext('state.cache.materialSpus[0].key', runtime), 'latest');
});

test('material images belong exclusively to the variety', () => {
  assert.doesNotMatch(script, /SKU 独立图片（可选）/);
  assert.doesNotMatch(script, /image_source==='sku'/);
  assert.doesNotMatch(script, /tax_series_sync_sku_images/);
  assert.match(script, /品种图库是该品种全部 SKU 的唯一图片源/);
});

test('variety directory keeps search and cascading filters in one toolbar', () => {
  assert.match(html, /class="filter-group catalog-variety-filters"/);
  assert.match(html, /id="catalogVarietyKeyword"[^>]*oninput="renderMaterialVarietiesPage\(\)"/);
  assert.match(html, /id="catalogVarietyTypeFilter"/);
  assert.match(html, /id="catalogVarietyCategoryFilter"/);
  assert.match(script, /formValue\('catalogVarietyKeyword'\)\.trim\(\)\.toLowerCase\(\)/);
  assert.match(script, /searchable\.includes\(keyword\)/);
});

test('variety directory search matches variety, category, and workbench shape', () => {
  const elements = {
    catalogVarietyKeyword: { value: '随形' },
    catalogVarietyTypeFilter: { value: '' },
    catalogVarietyCategoryFilter: { value: '' },
  };
  const runtime = adminRuntime(elements);
  vm.runInContext(`
    state.cache.materialOptions = {
      ...DEFAULT_MATERIAL_OPTIONS,
      bead_shapes: [
        { key: 'round', label: '圆珠' },
        { key: 'nugget', label: '随形' }
      ]
    };
    state.cache.materialTaxonomy = [
      { id: 'cat-bead', kind: 'category', top: 'bead', name: '幽灵水晶', enabled: true, series: [
        { id: 'green-phantom', name: '绿幽灵', enabled: true, material_params: { bead_shape: 'round' } }
      ] },
      { id: 'cat-accessory', kind: 'category', top: 'accessory', name: '幽灵配饰', enabled: true, series: [
        { id: 'red-nugget', name: '红幽灵', enabled: true, material_params: { bead_shape: 'nugget' } }
      ] }
    ];
  `, runtime);

  const rows = runtime.materialVarietyRows();

  assert.equal(rows.length, 1);
  assert.equal(rows[0].item.id, 'red-nugget');
});
