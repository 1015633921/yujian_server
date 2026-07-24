const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');

function loadWorkspacePage() {
  const workspacePath = path.join(root, 'miniprogram/pages/workspace/workspace.js');
  delete require.cache[require.resolve(workspacePath)];
  let pageConfig = null;
  global.Page = config => { pageConfig = config; };
  require(workspacePath);
  return pageConfig;
}

function pageInstance(page) {
  return Object.assign({}, page, {
    data: { ...page.data },
    setData(updates, callback) {
      this.data = { ...this.data, ...updates };
      if (callback) callback();
    }
  });
}

test('workspace onboarding waits for the workbench then progresses through five steps', () => {
  global.wx = {
    getStorageSync() { return false; },
    setStorageSync() {},
    nextTick(callback) { callback(); },
    createSelectorQuery() {
      return {
        in() { return this; },
        select() {
          return {
            boundingClientRect(callback) {
              callback(null);
              return { exec() {} };
            }
          };
        }
      };
    }
  };
  const instance = pageInstance(loadWorkspacePage());

  instance.initWorkspaceGuide();
  assert.equal(instance.data.showWorkspaceGuide, false);
  instance.maybeShowWorkspaceGuide();
  assert.equal(instance.data.showWorkspaceGuide, true);
  assert.equal(instance.data.workspaceGuideStep, 0);
  assert.equal(instance.data.activeWorkspaceGuide.target, 'wrist');
  assert.equal(instance.data.workspaceGuideSteps.length, 5);

  instance.workspaceGuideWaitingForWrist = true;
  instance.resumeWristGuideIfNeeded(true);
  assert.equal(instance.data.workspaceGuideStep, 1);
  assert.equal(instance.data.activeWorkspaceGuide.target, 'materials');

  for (let index = 2; index < 5; index += 1) instance.advanceWorkspaceGuide();
  assert.equal(instance.data.workspaceGuideStep, 4);
  instance.advanceWorkspaceGuide();
  assert.equal(instance.data.showWorkspaceGuide, false);
  assert.equal(instance.workspaceGuideDismissed, true);
});

test('workspace help keeps the replay entry and the onboarding highlights each core action', () => {
  const template = fs.readFileSync(path.join(root, 'miniprogram/pages/workspace/workspace.wxml'), 'utf8');
  const source = fs.readFileSync(path.join(root, 'miniprogram/pages/workspace/workspace.js'), 'utf8');
  const styles = fs.readFileSync(path.join(root, 'miniprogram/pages/workspace/workspace.wxss'), 'utf8');

  assert.match(template, /catchtap="restartWorkspaceGuide"/);
  assert.match(template, /workspace-onboarding-mask/);
  assert.match(template, /workspace-onboarding-focus/);
  assert.match(template, /guide-card-\{\{activeWorkspaceGuide\.target\}\}/);
  assert.match(template, /workspace-onboarding-next/);
  assert.match(template, /workspace-guide-anchor-tray/);
  assert.match(template, /workspace-guide-anchor-string/);
  assert.match(template, /workspace-guide-anchor-wrist/);
  assert.match(template, /workspace-guide-anchor-materials/);
  assert.match(template, /workspace-guide-anchor-checkout/);
  assert.match(source, /const WORKSPACE_GUIDE_STEPS = \[/);
  assert.match(source, /target: 'materials'/);
  assert.match(source, /target: 'tray'/);
  assert.match(source, /target: 'string'/);
  assert.match(source, /target: 'wrist'/);
  assert.match(source, /target: 'checkout'/);
  assert.match(source, /measureWorkspaceGuideFocus\(\)/);
  assert.match(source, /resumeWristGuideIfNeeded\(true\)/);
  assert.match(styles, /\.workspace-onboarding-mask/);
  assert.match(styles, /\.workspace-onboarding-focus/);
  assert.match(styles, /\.workspace-onboarding-card\.guide-card-materials/);
});
