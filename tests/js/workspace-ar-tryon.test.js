const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const repoRoot = path.resolve(__dirname, '../..');
const { buildBraceletLayout, itemAspectRatio, itemSizeMm } = require(
  path.resolve(repoRoot, 'miniprogram/package-ar/pages/ar-tryon/layout.js')
);

function loadPage(relativePath) {
  const absolutePath = path.resolve(repoRoot, relativePath);
  delete require.cache[require.resolve(absolutePath)];
  let pageConfig = null;
  global.Page = config => {
    pageConfig = config;
  };
  require(absolutePath);
  return pageConfig;
}

test('AR try-on layout preserves bead scale and separates front and back halves', () => {
  const items = Array.from({ length: 20 }, (_, index) => ({
    id: `bead-${index}`,
    size: index % 5 === 0 ? 12 : 10,
    image_url: `https://cdn.example.com/bead-${index}.webp`,
    material_params: {}
  }));
  const layout = buildBraceletLayout({
    items,
    width: 390,
    height: 844,
    centerX: 195,
    centerY: 360,
    scale: 1,
    rotation: 0
  });

  assert.equal(layout.length, items.length);
  assert.ok(layout.some(entry => entry.isBack && entry.opacity < 0.3));
  assert.ok(layout.some(entry => !entry.isBack && entry.opacity === 1));
  assert.ok(layout.every(entry => entry.x > 0 && entry.x < 390));
  assert.ok(layout.every(entry => entry.y > 0 && entry.y < 844));
  const large = layout.find(entry => entry.item.size === 12);
  const regular = layout.find(entry => entry.item.size === 10);
  assert.ok(large.width > regular.width);
});

test('AR try-on layout respects measured irregular accessory dimensions', () => {
  const accessory = {
    size: 10,
    material_params: {
      body_width_mm: 12,
      body_height_mm: 6
    }
  };

  assert.equal(itemSizeMm(accessory), 10);
  assert.equal(itemAspectRatio(accessory), 0.5);
  const [entry] = buildBraceletLayout({
    items: [accessory],
    width: 375,
    height: 667
  });
  assert.ok(entry.width > entry.height);
});

test('current release does not expose or package AR try-on', () => {
  const appConfig = JSON.parse(fs.readFileSync(
    path.resolve(repoRoot, 'miniprogram/app.json'),
    'utf8'
  ));
  const projectConfig = JSON.parse(fs.readFileSync(
    path.resolve(repoRoot, 'miniprogram/project.config.json'),
    'utf8'
  ));
  const workspaceSource = fs.readFileSync(
    path.resolve(repoRoot, 'miniprogram/pages/workspace/workspace.js'),
    'utf8'
  );
  const workspaceWxml = fs.readFileSync(
    path.resolve(repoRoot, 'miniprogram/pages/workspace/workspace.wxml'),
    'utf8'
  );
  const ignoredFolders = (projectConfig.packOptions && projectConfig.packOptions.ignore || [])
    .filter(item => item.type === 'folder')
    .map(item => item.value);

  assert.ok(!(appConfig.subPackages || []).some(item => item.root === 'package-ar'));
  assert.ok(ignoredFolders.includes('package-ar'));
  assert.doesNotMatch(workspaceSource, /openArTryOn|arTryOnDesign|package-ar/);
  assert.doesNotMatch(workspaceWxml, /AR试戴|plate-ar-btn|openArTryOn/);
});

test('AR try-on page is camera-based, locally composited, and contains no synthetic lighting', () => {
  const appConfig = JSON.parse(fs.readFileSync(
    path.resolve(repoRoot, 'miniprogram/app.json'),
    'utf8'
  ));
  const pageSource = fs.readFileSync(
    path.resolve(repoRoot, 'miniprogram/package-ar/pages/ar-tryon/ar-tryon.js'),
    'utf8'
  );
  const pageWxml = fs.readFileSync(
    path.resolve(repoRoot, 'miniprogram/package-ar/pages/ar-tryon/ar-tryon.wxml'),
    'utf8'
  );
  const pageWxss = fs.readFileSync(
    path.resolve(repoRoot, 'miniprogram/package-ar/pages/ar-tryon/ar-tryon.wxss'),
    'utf8'
  );

  const arPackage = (appConfig.subPackages || []).find(item => item.root === 'package-ar');
  assert.equal(arPackage, undefined);
  assert.match(pageWxml, /<camera/);
  assert.match(pageWxml, /bindinitdone="onCameraInitDone"/);
  assert.match(pageWxml, /catchtouchmove="onOverlayTouchMove"/);
  assert.match(pageSource, /takePhoto/);
  assert.match(pageSource, /canvasToTempFilePath/);
  assert.match(pageSource, /saveImageToPhotosAlbum/);
  assert.match(pageSource, /getPrivacySetting/);
  assert.match(pageWxml, /open-type="agreePrivacyAuthorization"/);
  assert.match(pageWxml, /bindagreeprivacyauthorization="onAgreePrivacyAuthorization"/);
  assert.match(pageWxml, /tryon-overlay-disabled/);
  assert.match(pageWxss, /\.camera-fallback\s*\{[^}]*z-index:\s*3/s);
  assert.match(pageWxss, /\.tryon-overlay-disabled\s*\{[^}]*pointer-events:\s*none/s);
  assert.doesNotMatch(pageSource, /uploadFile|request\(|StudioMetalLight|filter:/);
});

test('AR try-on asks for privacy consent before camera permission', async () => {
  const page = loadPage('miniprogram/package-ar/pages/ar-tryon/ar-tryon.js');
  const calls = [];
  global.wx = {
    getPrivacySetting(options) {
      calls.push('getPrivacySetting');
      options.success({
        needAuthorization: true,
        privacyContractName: '宇涧水晶隐私保护指引'
      });
    },
    getSetting(options) {
      calls.push('getSetting');
      options.success({ authSetting: {} });
    },
    authorize(options) {
      calls.push(`authorize:${options.scope}`);
      options.success();
    }
  };
  const instance = Object.assign({}, page, {
    data: { ...page.data },
    setData(patch) {
      Object.assign(this.data, patch);
    }
  });

  const waitingForConsent = await instance.requestCameraPermission();

  assert.equal(waitingForConsent, false);
  assert.deepEqual(calls, ['getPrivacySetting']);
  assert.equal(instance.data.privacyAuthorizationNeeded, true);
  assert.equal(instance.data.cameraAuthorized, false);

  const authorized = await instance.onAgreePrivacyAuthorization();

  assert.equal(authorized, true);
  assert.deepEqual(calls, [
    'getPrivacySetting',
    'authorize:scope.camera'
  ]);
  assert.equal(instance.data.privacyAuthorizationNeeded, false);
  assert.equal(instance.data.cameraRequested, true);
  assert.equal(instance.data.cameraAuthorized, false);

  instance.onCameraInitDone();

  assert.equal(instance.data.cameraAuthorized, true);
});

test('AR try-on waits without requesting camera until the privacy button is agreed', async () => {
  const page = loadPage('miniprogram/package-ar/pages/ar-tryon/ar-tryon.js');
  global.wx = {
    getPrivacySetting(options) {
      options.success({ needAuthorization: true });
    }
  };
  const instance = Object.assign({}, page, {
    data: { ...page.data },
    setData(patch) {
      Object.assign(this.data, patch);
    }
  });

  const authorized = await instance.requestCameraPermission();

  assert.equal(authorized, false);
  assert.equal(instance.data.cameraRequested, false);
  assert.equal(instance.data.privacyAuthorizationNeeded, true);
  assert.equal(instance.data.cameraError, '');
});

test('AR try-on fails closed when the privacy setting cannot be read', async () => {
  const page = loadPage('miniprogram/package-ar/pages/ar-tryon/ar-tryon.js');
  let cameraPermissionRequested = false;
  global.wx = {
    getPrivacySetting(options) {
      options.fail({ errMsg: 'getPrivacySetting:fail' });
    },
    authorize() {
      cameraPermissionRequested = true;
    }
  };
  const instance = Object.assign({}, page, {
    data: { ...page.data },
    setData(patch) {
      Object.assign(this.data, patch);
    }
  });

  const authorized = await instance.requestCameraPermission();

  assert.equal(authorized, false);
  assert.equal(cameraPermissionRequested, false);
  assert.equal(instance.data.privacyAuthorizationNeeded, true);
  assert.match(instance.data.cameraError, /读取失败/);
});

test('AR try-on exposes camera component errors and retries through settings after denial', async () => {
  const page = loadPage('miniprogram/package-ar/pages/ar-tryon/ar-tryon.js');
  let settingsOpened = false;
  global.wx = {
    getPrivacySetting(options) {
      options.success({ needAuthorization: false });
    },
    authorize(options) {
      options.success();
    },
    openSetting(options) {
      settingsOpened = true;
      options.success({ authSetting: { 'scope.camera': true } });
    }
  };
  const instance = Object.assign({}, page, {
    data: { ...page.data, cameraRequested: true },
    setData(patch) {
      Object.assign(this.data, patch);
    }
  });

  instance.onCameraError({
    detail: { errMsg: 'camera:fail auth deny' }
  });

  assert.equal(instance.data.cameraRequested, false);
  assert.equal(instance.data.cameraPermissionDenied, true);
  assert.match(instance.data.cameraError, /auth deny/);

  const retried = await instance.requestCameraPermission();

  assert.equal(retried, true);
  assert.equal(settingsOpened, true);
  assert.equal(instance.data.cameraRequested, true);
  assert.equal(instance.data.cameraError, '');
  instance.onCameraInitDone();
});
