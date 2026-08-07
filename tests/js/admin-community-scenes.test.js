const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const script = fs.readFileSync(path.join(root, 'static/admin/admin.js'), 'utf8');

function runtime(elements = {}) {
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
  return context;
}

test('community scene editor stores multiple unique tags in the compatible scene field', () => {
  const elements = {
    community_scene: { value: '通勤' },
    community_scene_tag_input: { value: '会议、约会、通勤', focus() {} },
    community_scene_tag_list: { innerHTML: '' },
  };
  const context = runtime(elements);

  context.addCommunitySceneTags();

  assert.equal(elements.community_scene.value, '通勤、会议、约会');
  assert.match(elements.community_scene_tag_list.innerHTML, /通勤/);
  assert.match(elements.community_scene_tag_list.innerHTML, /会议/);
  assert.match(elements.community_scene_tag_list.innerHTML, /约会/);
});

test('community scene editor renders the input as a tag control rather than a text field', () => {
  const context = runtime();
  const markup = context.communitySceneTagPicker('通勤、会议');

  assert.match(markup, /id="community_scene" type="hidden"/);
  assert.match(markup, /id="community_scene_tag_input"/);
  assert.match(markup, /onclick="addCommunitySceneTags\(\)"/);
  assert.match(markup, /移除/);
});
