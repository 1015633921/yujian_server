const { buildBraceletLayout } = require('./layout');

const DESIGN_STORAGE_KEY = 'arTryOnDesign';
const CAMERA_INIT_TIMEOUT_MS = 5000;

function touchPoint(touch = {}) {
  const x = Number(touch.clientX ?? touch.pageX ?? touch.x);
  const y = Number(touch.clientY ?? touch.pageY ?? touch.y);
  return {
    x: Number.isFinite(x) ? x : 0,
    y: Number.isFinite(y) ? y : 0
  };
}

function touchDistance(first, second) {
  return Math.hypot(second.x - first.x, second.y - first.y);
}

function touchAngle(first, second) {
  return Math.atan2(second.y - first.y, second.x - first.x);
}

Page({
  data: {
    safeTop: 24,
    safeBottom: 0,
    capsuleSafeRight: 96,
    cameraRequested: false,
    cameraAuthorized: false,
    cameraPermissionDenied: false,
    cameraError: '',
    privacyAuthorizationNeeded: false,
    privacyAuthorizationDenied: false,
    privacyContractName: '',
    hasDesign: false,
    itemCount: 0,
    wristSizeText: '16.0',
    scaleValue: 100,
    guideText: '将手腕放入框内',
    gestureActive: false,
    savingPhoto: false
  },

  onLoad() {
    const windowInfo = wx.getWindowInfo
      ? wx.getWindowInfo()
      : (wx.getSystemInfoSync ? wx.getSystemInfoSync() : {});
    const screenHeight = Number(windowInfo.screenHeight || windowInfo.windowHeight || 667);
    const windowWidth = Number(windowInfo.windowWidth) || 375;
    const safeArea = windowInfo.safeArea || {};
    let menuButtonRect = null;
    try {
      menuButtonRect = wx.getMenuButtonBoundingClientRect
        ? wx.getMenuButtonBoundingClientRect()
        : null;
    } catch (error) {
      menuButtonRect = null;
    }
    const capsuleSafeRight = menuButtonRect && Number(menuButtonRect.left) > 0
      ? Math.max(72, windowWidth - Number(menuButtonRect.left) + 10)
      : 96;
    this.viewport = {
      width: windowWidth,
      height: Number(windowInfo.windowHeight) || 667
    };
    this.setData({
      safeTop: Number(windowInfo.statusBarHeight) || 24,
      safeBottom: Math.max(0, screenHeight - Number(safeArea.bottom || screenHeight)),
      capsuleSafeRight
    });
    this.loadTryOnDesign();
    this.resolveCameraPermission();
  },

  onReady() {
    this.initTryOnCanvases();
    this.cameraContext = wx.createCameraContext ? wx.createCameraContext(this) : null;
  },

  onUnload() {
    if (this.overlayFrame && this.overlayCanvasState && this.overlayCanvasState.canvas) {
      const canvas = this.overlayCanvasState.canvas;
      if (canvas.cancelAnimationFrame) canvas.cancelAnimationFrame(this.overlayFrame);
    }
    clearTimeout(this.gestureEndTimer);
    clearTimeout(this.cameraInitTimer);
    this.overlayFrame = null;
    this.overlayCanvasState = null;
    this.exportCanvasState = null;
    this.overlayImageCache = Object.create(null);
    this.exportImageCache = Object.create(null);
  },

  loadTryOnDesign() {
    const payload = wx.getStorageSync(DESIGN_STORAGE_KEY) || {};
    const items = Array.isArray(payload.items)
      ? payload.items.filter(item => item && (item.image_url || item.name))
      : [];
    this.tryOnDesign = {
      ...payload,
      items
    };
    const wristSize = Number(payload.wristSize || payload.wrist_size_cm || 16);
    this.setData({
      hasDesign: items.length > 0,
      itemCount: items.length,
      wristSizeText: (Number.isFinite(wristSize) ? wristSize : 16).toFixed(1)
    });
  },

  resolveCameraPermission() {
    return this.resolvePrivacyAuthorization(false).then(authorized => {
      if (!authorized) return false;
      return this.resolveSystemCameraPermission();
    });
  },

  resolvePrivacyAuthorization(interactive) {
    if (!wx.getPrivacySetting) return Promise.resolve(true);
    return new Promise(resolve => {
      wx.getPrivacySetting({
        success: result => {
          const needAuthorization = !!(result && result.needAuthorization);
          const privacyContractName = String(result && result.privacyContractName || '');
          if (!needAuthorization) {
            this.setData({
              privacyAuthorizationNeeded: false,
              privacyAuthorizationDenied: false,
              privacyContractName
            });
            resolve(true);
            return;
          }
          this.setData({
            cameraAuthorized: false,
            privacyAuthorizationNeeded: true,
            privacyAuthorizationDenied: false,
            privacyContractName,
            cameraError: ''
          });
          if (!interactive) {
            resolve(false);
            return;
          }
          resolve(false);
        },
        fail: () => {
          this.setData({
            cameraAuthorized: false,
            privacyAuthorizationNeeded: true,
            cameraError: '隐私授权状态读取失败，请稍后重试'
          });
          resolve(false);
        }
      });
    });
  },

  resolveSystemCameraPermission() {
    if (!wx.getSetting) {
      return Promise.resolve(false);
    }
    return new Promise(resolve => {
      wx.getSetting({
        success: result => {
          const authorized = !!(result.authSetting && result.authSetting['scope.camera']);
          const denied = result.authSetting && result.authSetting['scope.camera'] === false;
          this.setData({
            cameraPermissionDenied: denied,
            cameraError: denied ? '请在设置中允许使用相机' : ''
          });
          if (!authorized) {
            resolve(false);
            return;
          }
          Promise.resolve(this.startCameraComponent()).then(resolve);
        },
        fail: () => resolve(false)
      });
    });
  },

  requestCameraPermission() {
    return this.resolvePrivacyAuthorization(true).then(authorized => {
      if (!authorized) return false;
      return this.requestSystemCameraPermission();
    });
  },

  onAgreePrivacyAuthorization() {
    this.setData({
      privacyAuthorizationNeeded: false,
      privacyAuthorizationDenied: false,
      cameraError: ''
    });
    return this.requestSystemCameraPermission();
  },

  requestSystemCameraPermission() {
    if (this.data.cameraPermissionDenied && wx.openSetting) {
      return new Promise(resolve => {
        wx.openSetting({
          success: result => {
            const authorized = !!(result.authSetting && result.authSetting['scope.camera']);
            this.setData({
              cameraPermissionDenied: !authorized,
              cameraError: authorized ? '' : '请在设置中允许使用相机'
            });
            if (!authorized) {
              resolve(false);
              return;
            }
            Promise.resolve(this.startCameraComponent()).then(resolve);
          },
          fail: () => resolve(false)
        });
      });
    }
    if (!wx.authorize) {
      this.setData({ cameraError: '当前微信版本暂不支持相机授权，请升级微信后重试' });
      return Promise.resolve(false);
    }
    return new Promise(resolve => {
      wx.authorize({
        scope: 'scope.camera',
        success: () => {
          Promise.resolve(this.startCameraComponent()).then(resolve);
        },
        fail: error => {
          const errMsg = String(error && error.errMsg || 'authorize:fail');
          this.setData({
            cameraRequested: false,
            cameraAuthorized: false,
            cameraPermissionDenied: /deny|denied/i.test(errMsg),
            cameraError: `摄像头授权失败：${errMsg}`
          });
          resolve(false);
        }
      });
    });
  },

  startCameraComponent() {
    clearTimeout(this.cameraInitTimer);
    this.setData({
      cameraRequested: true,
      cameraAuthorized: false,
      cameraError: ''
    });
    this.cameraInitTimer = setTimeout(() => {
      if (this.data.cameraAuthorized || !this.data.cameraRequested) return;
      this.setData({
        cameraRequested: false,
        cameraError: '相机初始化超时，请关闭占用摄像头的应用后重试'
      });
    }, CAMERA_INIT_TIMEOUT_MS);
    return Promise.resolve(true);
  },

  onCameraInitDone() {
    clearTimeout(this.cameraInitTimer);
    this.setData({
      cameraRequested: true,
      cameraAuthorized: true,
      cameraPermissionDenied: false,
      cameraError: ''
    });
  },

  onCameraError(event) {
    clearTimeout(this.cameraInitTimer);
    const detail = event && event.detail || {};
    const errMsg = String(detail.errMsg || '当前设备无法打开相机');
    this.setData({
      cameraRequested: false,
      cameraAuthorized: false,
      cameraPermissionDenied: /auth|authorize|permission|deny/i.test(errMsg),
      cameraError: errMsg
    });
  },

  initTryOnCanvases() {
    const query = wx.createSelectorQuery().in(this);
    query.select('#arOverlayCanvas').fields({ node: true, size: true });
    query.select('#arExportCanvas').fields({ node: true, size: true });
    query.exec(result => {
      this.overlayCanvasState = this.setupCanvasState(result && result[0]);
      this.exportCanvasState = this.setupCanvasState(result && result[1]);
      const width = this.overlayCanvasState
        ? this.overlayCanvasState.width
        : this.viewport.width;
      const height = this.overlayCanvasState
        ? this.overlayCanvasState.height
        : this.viewport.height;
      this.tryOnTransform = {
        centerX: width / 2,
        centerY: height * 0.43,
        scale: 1,
        rotation: 0
      };
      this.overlayImageCache = Object.create(null);
      this.exportImageCache = Object.create(null);
      this.preloadDesignImages(this.overlayCanvasState, this.overlayImageCache)
        .finally(() => this.requestOverlayRender());
    });
  },

  setupCanvasState(info) {
    if (!info || !info.node) return null;
    const canvas = info.node;
    const width = Math.max(1, Number(info.width) || this.viewport.width);
    const height = Math.max(1, Number(info.height) || this.viewport.height);
    const dpr = Math.min(3, Number(wx.getWindowInfo && wx.getWindowInfo().pixelRatio) || 2);
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    return { canvas, ctx, width, height, dpr };
  },

  imageUrls() {
    const urls = [];
    (this.tryOnDesign && this.tryOnDesign.items || []).forEach(item => {
      if (item.image_url) urls.push(item.image_url);
      const slots = item.placement && item.placement.bead_caps || {};
      ['left', 'right'].forEach(side => {
        if (slots[side] && slots[side].image_url) urls.push(slots[side].image_url);
      });
    });
    return Array.from(new Set(urls));
  },

  preloadDesignImages(state, cache) {
    if (!state || !state.canvas) return Promise.resolve();
    return Promise.all(this.imageUrls().map(url => this.loadCanvasImage(state, cache, url)))
      .then(() => undefined);
  },

  loadCanvasImage(state, cache, url) {
    if (!state || !state.canvas || !url) return Promise.resolve(null);
    const current = cache[url];
    if (current && current.loaded) return Promise.resolve(current.image);
    if (current && current.promise) return current.promise;
    const image = state.canvas.createImage();
    const entry = { image, loaded: false, failed: false, promise: null };
    entry.promise = new Promise(resolve => {
      image.onload = () => {
        entry.loaded = true;
        entry.promise = null;
        resolve(image);
        if (state === this.overlayCanvasState) this.requestOverlayRender();
      };
      image.onerror = () => {
        entry.failed = true;
        entry.promise = null;
        resolve(null);
      };
      image.src = url;
    });
    cache[url] = entry;
    return entry.promise;
  },

  requestOverlayRender() {
    const state = this.overlayCanvasState;
    if (!state || this.overlayFrame) return;
    const callback = () => {
      this.overlayFrame = null;
      this.renderTryOnScene(state, this.overlayImageCache);
    };
    this.overlayFrame = state.canvas.requestAnimationFrame
      ? state.canvas.requestAnimationFrame(callback)
      : setTimeout(callback, 16);
  },

  renderTryOnScene(state, cache) {
    if (!state || !state.ctx) return;
    const ctx = state.ctx;
    ctx.clearRect(0, 0, state.width, state.height);
    if (!this.data.hasDesign) return;
    const transform = this.tryOnTransform || {};
    const layout = buildBraceletLayout({
      items: this.tryOnDesign.items,
      width: state.width,
      height: state.height,
      centerX: transform.centerX,
      centerY: transform.centerY,
      scale: transform.scale,
      rotation: transform.rotation
    });
    layout.forEach(entry => this.drawTryOnItem(ctx, entry, cache));
  },

  drawTryOnItem(ctx, entry, cache) {
    const item = entry.item || {};
    const cached = cache[item.image_url];
    const image = cached && cached.loaded ? cached.image : null;
    ctx.save();
    ctx.globalAlpha = entry.opacity;
    ctx.translate(entry.x, entry.y);
    ctx.rotate(entry.drawRotation);
    if (image) {
      ctx.drawImage(
        image,
        -entry.width / 2,
        -entry.height / 2,
        entry.width,
        entry.height
      );
    } else {
      ctx.fillStyle = entry.isBack ? 'rgba(230, 228, 222, 0.20)' : 'rgba(238, 236, 231, 0.82)';
      ctx.beginPath();
      ctx.ellipse(0, 0, entry.width / 2, entry.height / 2, 0, 0, Math.PI * 2);
      ctx.fill();
      if (item.image_url && !cached) {
        this.loadCanvasImage(this.overlayCanvasState, cache, item.image_url);
      }
    }
    ctx.restore();
    this.drawBeadCaps(ctx, entry, cache);
  },

  drawBeadCaps(ctx, entry, cache) {
    const slots = entry.item && entry.item.placement && entry.item.placement.bead_caps || {};
    ['left', 'right'].forEach(side => {
      const cap = slots[side];
      if (!cap || !cap.image_url) return;
      const cached = cache[cap.image_url];
      const image = cached && cached.loaded ? cached.image : null;
      if (!image) return;
      const direction = side === 'left' ? -1 : 1;
      const capSize = Math.max(7, Math.min(15, entry.height * 0.42));
      ctx.save();
      ctx.globalAlpha = entry.opacity;
      ctx.translate(entry.x, entry.y);
      ctx.rotate(entry.drawRotation);
      ctx.drawImage(
        image,
        direction * (entry.width / 2 + capSize * 0.24) - capSize / 2,
        -capSize / 2,
        capSize,
        capSize
      );
      ctx.restore();
    });
  },

  onOverlayTouchStart(event) {
    if (!this.data.hasDesign) return;
    const touches = Array.from(event.touches || []).map(touchPoint);
    if (!touches.length) return;
    clearTimeout(this.gestureEndTimer);
    const transform = this.tryOnTransform || {};
    if (touches.length >= 2) {
      this.gestureState = {
        type: 'transform',
        distance: Math.max(1, touchDistance(touches[0], touches[1])),
        angle: touchAngle(touches[0], touches[1]),
        scale: Number(transform.scale) || 1,
        rotation: Number(transform.rotation) || 0
      };
    } else {
      this.gestureState = {
        type: 'move',
        point: touches[0],
        centerX: Number(transform.centerX) || this.viewport.width / 2,
        centerY: Number(transform.centerY) || this.viewport.height * 0.43
      };
    }
    this.setData({ gestureActive: true, guideText: '正在校准位置' });
  },

  onOverlayTouchMove(event) {
    const state = this.gestureState;
    const touches = Array.from(event.touches || []).map(touchPoint);
    if (!state || !touches.length) return;
    if (state.type === 'transform' && touches.length >= 2) {
      const distance = Math.max(1, touchDistance(touches[0], touches[1]));
      const angle = touchAngle(touches[0], touches[1]);
      const scale = Math.max(0.58, Math.min(1.48, state.scale * distance / state.distance));
      this.tryOnTransform.scale = scale;
      this.tryOnTransform.rotation = state.rotation + angle - state.angle;
      this.setData({ scaleValue: Math.round(scale * 100) });
    } else if (state.type === 'move') {
      const point = touches[0];
      this.tryOnTransform.centerX = state.centerX + point.x - state.point.x;
      this.tryOnTransform.centerY = state.centerY + point.y - state.point.y;
    }
    this.requestOverlayRender();
  },

  onOverlayTouchEnd() {
    this.gestureState = null;
    clearTimeout(this.gestureEndTimer);
    this.gestureEndTimer = setTimeout(() => {
      this.setData({
        gestureActive: false,
        guideText: '将手腕放入框内'
      });
    }, 180);
  },

  onScaleChanging(event) {
    const value = Math.max(58, Math.min(148, Number(event.detail && event.detail.value) || 100));
    if (!this.tryOnTransform) return;
    this.tryOnTransform.scale = value / 100;
    this.setData({ scaleValue: value });
    this.requestOverlayRender();
  },

  resetCalibration() {
    const state = this.overlayCanvasState;
    if (!state) return;
    this.tryOnTransform = {
      centerX: state.width / 2,
      centerY: state.height * 0.43,
      scale: 1,
      rotation: 0
    };
    this.setData({
      scaleValue: 100,
      guideText: '将手腕放入框内'
    });
    this.requestOverlayRender();
  },

  captureTryOn() {
    if (this.data.savingPhoto || !this.cameraContext || !this.exportCanvasState) return;
    this.setData({ savingPhoto: true });
    this.takeCameraPhoto()
      .then(photoPath => this.composeTryOnPhoto(photoPath))
      .then(outputPath => this.saveTryOnPhoto(outputPath))
      .catch(error => {
        wx.showToast({
          title: error && error.message || '试戴照片生成失败',
          icon: 'none'
        });
      })
      .finally(() => this.setData({ savingPhoto: false }));
  },

  takeCameraPhoto() {
    return new Promise((resolve, reject) => {
      this.cameraContext.takePhoto({
        quality: 'high',
        success: result => resolve(result.tempImagePath),
        fail: error => reject(new Error(error && error.errMsg || '相机拍照失败'))
      });
    });
  },

  async composeTryOnPhoto(photoPath) {
    const state = this.exportCanvasState;
    const cache = this.exportImageCache;
    const photo = await this.loadCanvasImage(state, cache, photoPath);
    if (!photo) throw new Error('相机照片读取失败');
    await this.preloadDesignImages(state, cache);
    const ctx = state.ctx;
    const photoWidth = Number(photo.width) || state.width;
    const photoHeight = Number(photo.height) || state.height;
    const scale = Math.max(state.width / photoWidth, state.height / photoHeight);
    const drawWidth = photoWidth * scale;
    const drawHeight = photoHeight * scale;
    ctx.clearRect(0, 0, state.width, state.height);
    ctx.drawImage(
      photo,
      (state.width - drawWidth) / 2,
      (state.height - drawHeight) / 2,
      drawWidth,
      drawHeight
    );
    const layout = buildBraceletLayout({
      items: this.tryOnDesign.items,
      width: state.width,
      height: state.height,
      ...this.tryOnTransform
    });
    layout.forEach(entry => this.drawTryOnItem(ctx, entry, cache));
    return new Promise((resolve, reject) => {
      wx.canvasToTempFilePath({
        canvas: state.canvas,
        x: 0,
        y: 0,
        width: state.width,
        height: state.height,
        destWidth: Math.round(state.width * state.dpr),
        destHeight: Math.round(state.height * state.dpr),
        fileType: 'jpg',
        quality: 0.92,
        success: result => resolve(result.tempFilePath),
        fail: error => reject(new Error(error && error.errMsg || '照片合成失败'))
      }, this);
    });
  },

  saveTryOnPhoto(filePath) {
    return new Promise((resolve, reject) => {
      wx.saveImageToPhotosAlbum({
        filePath,
        success: () => {
          wx.showToast({ title: '已保存到相册', icon: 'success' });
          resolve(filePath);
        },
        fail: error => {
          if (wx.previewImage) wx.previewImage({ urls: [filePath], current: filePath });
          reject(new Error(error && error.errMsg && error.errMsg.includes('auth')
            ? '请允许保存到相册'
            : '已生成照片，可长按预览图保存'));
        }
      });
    });
  },

  showHelp() {
    wx.showModal({
      title: 'AR 试戴说明',
      content: '把手腕放在虚线框内。单指拖动手串，双指调整大小和角度。第一版采用手动校准，背面珠子会弱化显示。',
      showCancel: false,
      confirmText: '知道了'
    });
  },

  goBack() {
    wx.navigateBack({
      delta: 1,
      fail: () => wx.switchTab({ url: '/pages/workspace/workspace' })
    });
  }
});
