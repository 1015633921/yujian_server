const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');

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

test('workspace material cards expose a long-press detail entry without replacing tap-to-add', () => {
  const wxml = fs.readFileSync(path.join(root, 'miniprogram/pages/workspace/workspace.wxml'), 'utf8');
  const wxss = fs.readFileSync(path.join(root, 'miniprogram/pages/workspace/workspace.wxss'), 'utf8');

  assert.match(wxml, /bindtap="addMaterial"[\s\S]*bindlongpress="openMaterialDetail"/);
  assert.match(wxml, /wx:if="\{\{showMaterialDetail\}\}"/);
  assert.match(wxml, /catchtap="addMaterialFromDetail"/);
  assert.match(wxss, /\.material-detail-sheet/);
});

test('workspace material detail uses catalog data and suppresses a long-press ghost tap', () => {
  const page = loadWorkspacePage();
  const material = {
    id: 'crystal-a',
    top: 'bead',
    name: '白水晶',
    category: '圆珠',
    series: '白水晶',
    price: 12.5,
    size: 8,
    color: '#d6d6d6',
    description: '通透清爽的基础圆珠，适合做日常搭配的底色。',
    story: '常被用作简洁风格的基础材质。',
    effects: ['清透感', '舒缓氛围'],
    image_urls: ['https://example.com/a.webp', 'https://example.com/b.webp']
  };
  const instance = Object.assign({}, page, {
    data: { ...page.data, visibleMaterials: [material] },
    materialCatalog: [material],
    setData(updates) {
      this.data = { ...this.data, ...updates };
    }
  });
  instance.rebuildMaterialLookup(instance.materialCatalog, { resetDesignCaches: false });

  instance.openMaterialDetail({ currentTarget: { dataset: { id: material.id } } });

  assert.equal(instance.data.showMaterialDetail, true);
  assert.equal(instance.data.materialDetail.name, '白水晶');
  assert.deepEqual(instance.data.materialDetail.images, material.image_urls);
  assert.equal(instance.data.materialDetail.introduction, material.description);
  assert.equal(instance.data.materialDetail.story, material.story);
  assert.deepEqual(instance.data.materialDetail.effects, material.effects);
  assert.match(instance.data.materialDetail.priceText, /¥12\.50 \/ 颗/);
  assert.match(instance.data.materialDetail.fields.find(item => item.label === '规格').value, /8mm/);

  instance.lastMaterialLongPress = { id: material.id, at: Date.now() };
  instance.findMaterialById = () => {
    throw new Error('long-press ghost tap must return before material selection');
  };
  assert.doesNotThrow(() => instance.addMaterial({
    currentTarget: { dataset: { id: material.id, index: 0 } }
  }));
});
