const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const script = fs.readFileSync(path.join(root, 'static/admin/admin.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'static/admin/index.html'), 'utf8');

function runtime(elements = {}) {
  const context = {
    window: { location: { pathname: '/test-api/admin' } },
    localStorage: { getItem: () => '' },
    document: { getElementById: id => elements[id] || null },
    console,
    URLSearchParams,
    setTimeout,
    clearTimeout,
  };
  vm.createContext(context);
  vm.runInContext(script, context);
  return context;
}

test('material asset alpha bounds finds visible subject and transparency', () => {
  const context = runtime();
  const pixels = new Uint8ClampedArray(6 * 4 * 4);
  for (let y = 1; y <= 2; y += 1) {
    for (let x = 2; x <= 4; x += 1) pixels[(y * 6 + x) * 4 + 3] = 255;
  }

  const bounds = context.materialAssetAlphaBounds(pixels, 6, 4);

  assert.equal(bounds.left, 2);
  assert.equal(bounds.right, 4);
  assert.equal(bounds.top, 1);
  assert.equal(bounds.bottom, 2);
  assert.equal(bounds.width, 3);
  assert.equal(bounds.height, 2);
  assert.equal(bounds.subjectPixels, 6);
  assert.equal(bounds.transparentPixels, 18);
});

test('material asset placement centers the subject at the configured fill', () => {
  const context = runtime();

  const placement = context.materialAssetPlacement({ width: 1000, height: 500 }, 512, 0.985);

  assert.equal(placement.width, 504);
  assert.equal(placement.height, 252);
  assert.equal(placement.x, 4);
  assert.equal(placement.y, 130);
});

test('material asset filenames use natural numeric order', () => {
  const context = runtime();
  const names = ['IMG_10.png', 'IMG_2.png', 'IMG_1.png'];

  names.sort(context.materialAssetNaturalCompare);

  assert.deepEqual(names, ['IMG_1.png', 'IMG_2.png', 'IMG_10.png']);
});

test('admin exposes a dedicated material asset workbench', () => {
  assert.match(html, /data-page="materialAssets"/);
  assert.match(html, /id="materialAssetFiles"[^>]+multiple/);
  assert.match(html, /id="materialAssetTop"/);
  assert.match(html, /id="materialAssetCategory"/);
  assert.match(html, /id="materialAssetSeries"/);
  assert.match(html, /id="materialAssetUploadButton"/);
  assert.match(html, /id="materialAssetBindButton"/);
  assert.doesNotMatch(html, /id="materialAssetSyncSkus"/);
  assert.match(html, /品种图库是全部 SKU 的唯一图片源/);
  assert.match(script, /不影响主图/);
});

test('variety primary image uses a square preview without cropping the image', () => {
  const context = runtime();

  const markup = context.imageUploadField(
    'tax_series_image',
    '品种主图 / CDN 图片',
    'https://cdn.example.com/variety.webp',
    'material',
  );
  const stylesheet = fs.readFileSync(path.join(root, 'static/admin/admin.css'), 'utf8');

  assert.match(markup, /class="upload-preview material-primary-preview /);
  assert.match(stylesheet, /\.upload-preview\.material-primary-preview\{aspect-ratio:1;min-height:0\}/);
  assert.match(stylesheet, /\.upload-preview\.material-primary-preview img\{width:100%;height:100%;max-height:none;object-fit:contain\}/);
});

test('gallery image can fill the primary image without changing gallery order', () => {
  const classList = { add() {}, remove() {}, toggle() {} };
  const elements = {
    tax_series_images: { value: 'https://cdn.example.com/a.webp\nhttps://cdn.example.com/b.webp' },
    tax_series_image: { value: 'https://cdn.example.com/a.webp' },
    tax_series_image_preview: { classList, innerHTML: '' },
    tax_series_images_gallery: { innerHTML: '' },
    toast: { classList, textContent: '' },
  };
  const context = runtime(elements);

  context.setMaterialImageList('tax_series_images', [
    'https://cdn.example.com/a.webp',
    'https://cdn.example.com/b.webp',
  ]);
  context.selectMaterialPrimaryImage('tax_series_images', 1);

  assert.equal(elements.tax_series_image.value, 'https://cdn.example.com/b.webp');
  assert.equal(
    elements.tax_series_images.value,
    'https://cdn.example.com/a.webp\nhttps://cdn.example.com/b.webp',
  );
  assert.doesNotMatch(elements.tax_series_images_gallery.innerHTML, /is-primary|当前主图|主图<\/span>/);
  assert.match(elements.tax_series_images_gallery.innerHTML, /用作主图/);
});

test('removing the primary image from the gallery keeps the primary field unchanged', () => {
  const classList = { add() {}, remove() {}, toggle() {} };
  const elements = {
    tax_series_images: { value: 'https://cdn.example.com/a.webp\nhttps://cdn.example.com/b.webp' },
    tax_series_image: { value: 'https://cdn.example.com/a.webp' },
    tax_series_image_preview: { classList, innerHTML: '<img>' },
    tax_series_images_gallery: { innerHTML: '' },
    toast: { classList, textContent: '' },
  };
  const context = runtime(elements);

  context.removeMaterialImage('tax_series_images', 0);

  assert.equal(elements.tax_series_image.value, 'https://cdn.example.com/a.webp');
  assert.equal(elements.tax_series_images.value, 'https://cdn.example.com/b.webp');
  assert.match(elements.tax_series_image_preview.innerHTML, /img/);
  assert.equal(elements.toast.textContent, '已从图库移除，主图链接不受影响');
});

test('adding gallery images does not populate an empty primary field', () => {
  const classList = { add() {}, remove() {}, toggle() {} };
  const elements = {
    tax_series_images: { value: '' },
    tax_series_image: { value: '' },
    tax_series_image_preview: { classList, innerHTML: '' },
    tax_series_images_gallery: { innerHTML: '' },
    toast: { classList, textContent: '' },
  };
  const context = runtime(elements);

  context.setMaterialImageList('tax_series_images', ['https://cdn.example.com/gallery.webp']);

  assert.equal(elements.tax_series_image.value, '');
  assert.equal(elements.tax_series_images.value, 'https://cdn.example.com/gallery.webp');
});
