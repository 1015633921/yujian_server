const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const script = fs.readFileSync(path.join(root, 'static/admin/admin.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'static/admin/index.html'), 'utf8');
const css = fs.readFileSync(path.join(root, 'static/admin/admin.css'), 'utf8');

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

test('material category table keeps a compact selector without adding an image column', () => {
  assert.match(script, /class="material-category-check"/);
  assert.doesNotMatch(script, /material-category-image/);
  assert.match(css, /#materialCategoriesTable \.material-category-check\{width:34px/);
});

test('SKU group shortcuts load the material taxonomy before looking up a category or variety', () => {
  const seriesShortcut = script.indexOf('async function quickEditMaterialSeriesFromGroup(key){');
  const categoryShortcut = script.indexOf('async function quickEditMaterialCategoryFromGroup(key){');
  assert.ok(seriesShortcut >= 0);
  assert.ok(categoryShortcut >= 0);
  assert.match(script.slice(seriesShortcut, seriesShortcut + 320), /await ensureMaterialAdminMeta\(\);[\s\S]*findMaterialSeriesTaxonomy/);
  assert.match(script.slice(categoryShortcut, categoryShortcut + 260), /await ensureMaterialAdminMeta\(\);[\s\S]*categoryForName/);
});

test('editing a SKU that is no longer in the current list never opens the new-SKU form', async () => {
  const classList = { add() {}, remove() {} };
  const runtime = adminRuntime({ toast: { textContent: '', classList } });
  runtime.ensureMaterialAdminMeta = async () => {};
  runtime.ensureMaterialRefs = async () => {};
  runtime.renderMaterial = () => assert.fail('missing SKU must not open a blank material form');

  await runtime.editMaterial('stale-material-id');

  assert.match(vm.runInContext("$('toast').textContent", runtime), /已更新或不存在/);
});

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

test('batch enable explains that zero-stock SKUs need replenishment before enabling', async () => {
  const classList = { add() {}, remove() {} };
  const elements = { toast: { textContent: '', classList } };
  const runtime = adminRuntime(elements);

  vm.runInContext(`
    state.cache.materials = [
      { sku: { id: 'empty-sku', name: '缺货隔珠', stock: 0 } },
      { sku: { id: 'ready-sku', name: '有货隔珠', stock: 5 } }
    ];
    state.materialUi.selected.add('empty-sku');
    state.materialUi.selected.add('ready-sku');
  `, runtime);

  await runtime.batchMaterials('enable');

  assert.match(elements.toast.textContent, /缺货隔珠/);
  assert.match(elements.toast.textContent, /请先补充库存后再批量启用/);
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

test('SKU search submits immediately on Enter and blur, with a loading indicator while requested', async () => {
  const classList = { add() {}, remove() {} };
  const elements = Object.fromEntries([
    'materialKeyword', 'materialTop', 'materialCategory', 'materialElement', 'materialStatus',
    'materialStockState', 'materialMargin', 'materialQuality', 'materialSpecState'
  ].map(id => [id, { value: '' }]));
  elements.materialSearchLoading = { hidden: true, setAttribute() {} };
  elements.materialsTable = { setAttribute() {} };
  elements.toast = { textContent: '', classList };
  const runtime = adminRuntime(elements);
  const requests = [];
  runtime.ensureMaterialAdminMeta = async () => {};
  runtime.api = () => new Promise(resolve => requests.push(resolve));
  runtime.renderMaterialsTable = () => {};

  let prevented = false;
  runtime.handleMaterialKeywordKeydown({ key: 'Enter', preventDefault() { prevented = true; } });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(prevented, true);
  assert.equal(requests.length, 1);
  assert.equal(elements.materialSearchLoading.hidden, false);
  assert.equal(vm.runInContext('state.materialUi.loading', runtime), true);

  requests.shift()({ items: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 1 } });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(elements.materialSearchLoading.hidden, true);
  assert.equal(vm.runInContext('state.materialUi.loading', runtime), false);

  runtime.handleMaterialKeywordBlur();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(requests.length, 1);
  requests.shift()({ items: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 1 } });
  assert.match(html, /onkeydown="handleMaterialKeywordKeydown\(event\)"/);
  assert.match(html, /onblur="handleMaterialKeywordBlur\(\)"/);
  assert.match(html, /id="materialSearchLoading"/);
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

test('material categories support single and batch deletion through the empty-category guard', () => {
  assert.match(html, /id="materialCategoryDeleteButton"/);
  assert.match(script, /function batchDeleteMaterialCategories\(\)/);
  assert.match(script, /function deleteEmptyMaterialCategory\(id,name=''\)/);
  assert.match(script, /categories\/batch-delete/);
  assert.match(script, /仅没有品种和 SKU 的空分类/);
});

test('SKU and every material directory level expose guarded deletion actions', () => {
  assert.match(script, /SKU 仍在启用，请先停用后再删除/);
  assert.match(script, /确定删除这个已停用 SKU 吗/);
  assert.match(script, /deleteEmptyMaterialType/);
  assert.match(script, /material-types\/batch-delete/);
  assert.match(script, /deleteEmptyMaterialSeries/);
  assert.match(script, /series\/batch-delete/);
});

test('variety rows create new specifications with their category and material code prefilled', () => {
  const runtime = adminRuntime();
  runtime.ensureMaterialAdminMeta = async () => {};
  let form;
  runtime.renderMaterial = value => { form = value; };
  vm.runInContext(`
    state.cache.materialTaxonomy = [{
      id: 'cat-rutilated', kind: 'category', top: 'bead', name: '发晶', enabled: true, series: [{
        id: 'series-silver-rutilated', parent_id: 'cat-rutilated', kind: 'series', top: 'bead',
        name: '银发晶', material_code: 'silver_rutilated_quartz', enabled: true
      }]
    }];
  `, runtime);

  return runtime.newMaterialSpecForSeries('series-silver-rutilated', 'cat-rutilated').then(() => {
    assert.equal(form.sku.category, '发晶');
    assert.equal(form.sku.series, '银发晶');
    assert.equal(form.sku.material_code, 'silver_rutilated_quartz');
    assert.match(script, /新增规格/);
  });
});

test('variety directory keeps search and cascading filters in one toolbar', () => {
  assert.match(html, /class="filter-group catalog-variety-filters"/);
  assert.match(html, /id="catalogVarietyKeyword"[^>]*oninput="renderMaterialVarietiesPage\(\)"/);
  assert.match(html, /id="catalogVarietyTypeFilter"/);
  assert.match(html, /id="catalogVarietyCategoryFilter"/);
  assert.match(html, /id="catalogVarietyStatusFilter"[^>]*onchange="renderMaterialVarietiesPage\(\)"/);
  assert.match(script, /formValue\('catalogVarietyKeyword'\)\.trim\(\)\.toLowerCase\(\)/);
  assert.match(script, /formValue\('catalogVarietyStatusFilter'\)/);
  assert.match(script, /searchable\.includes\(keyword\)/);
});

test('variety directory search matches variety, category, and workbench shape', () => {
  const elements = {
    catalogVarietyKeyword: { value: '随形' },
    catalogVarietyTypeFilter: { value: '' },
    catalogVarietyCategoryFilter: { value: '' },
    catalogVarietyStatusFilter: { value: '' },
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

test('variety directory filters enabled and disabled entries by status', () => {
  const elements = {
    catalogVarietyKeyword: { value: '' },
    catalogVarietyTypeFilter: { value: '' },
    catalogVarietyCategoryFilter: { value: '' },
    catalogVarietyStatusFilter: { value: 'disabled' },
  };
  const runtime = adminRuntime(elements);
  vm.runInContext(`
    state.cache.materialTaxonomy = [{ id: 'cat', kind: 'category', top: 'bead', name: '水晶', enabled: true, series: [
      { id: 'enabled', name: '白水晶', enabled: true },
      { id: 'disabled', name: '黑曜石', enabled: false }
    ] }];
  `, runtime);

  assert.deepEqual(Array.from(runtime.materialVarietyRows(), row => row.item.id), ['disabled']);
  elements.catalogVarietyStatusFilter.value = 'enabled';
  assert.deepEqual(Array.from(runtime.materialVarietyRows(), row => row.item.id), ['enabled']);
});
