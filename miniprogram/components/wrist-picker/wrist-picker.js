const DEFAULT_MIN = 10;
const DEFAULT_MAX = 25;
const STEP = 0.1;
const TICK_RPX = 22;

Component({
  properties: {
    visible: { type: Boolean, value: false },
    value: { type: Number, value: 16 },
    min: { type: Number, value: DEFAULT_MIN },
    max: { type: Number, value: DEFAULT_MAX },
    subtitle: {
      type: String,
      value: '设置腕围，系统会同步更新当前方案适配参考。'
    }
  },

  data: {
    ticks: [],
    displayValue: '16.0',
    rangeText: '10.0–25.0 cm',
    tickWidth: 9,
    sidePadding: 0,
    scrollLeft: 0
  },

  observers: {
    'visible,value,min,max': function onPickerStateChanged(visible) {
      if (!visible) return;
      wx.nextTick(() => this.prepare(this.properties.value));
    }
  },

  lifetimes: {
    detached() {
      clearTimeout(this.snapTimer);
    }
  },

  methods: {
    stopPropagation() {},

    close() {
      this.triggerEvent('close');
    },

    windowWidth() {
      if (typeof wx.getWindowInfo === 'function') {
        return Number(wx.getWindowInfo().windowWidth) || 375;
      }
      return Number(wx.getSystemInfoSync().windowWidth) || 375;
    },

    normalized(value) {
      const min = Number(this.properties.min) || DEFAULT_MIN;
      const max = Number(this.properties.max) || DEFAULT_MAX;
      const numeric = Number(value);
      return Math.round(Math.max(min, Math.min(max, Number.isFinite(numeric) ? numeric : 16)) * 10) / 10;
    },

    format(value) {
      return this.normalized(value).toFixed(1);
    },

    buildTicks() {
      const min = Number(this.properties.min) || DEFAULT_MIN;
      const max = Number(this.properties.max) || DEFAULT_MAX;
      const total = Math.round((max - min) / STEP);
      return Array.from({ length: total + 1 }, (_, index) => ({
        index,
        label: index % 10 === 0 ? String(Math.round(min + index * STEP)) : '',
        className: index % 10 === 0 ? 'major' : (index % 5 === 0 ? 'middle' : 'minor')
      }));
    },

    valueToScrollLeft(value, tickWidth = this.data.tickWidth) {
      const min = Number(this.properties.min) || DEFAULT_MIN;
      return Math.round((this.normalized(value) - min) * 10 * tickWidth);
    },

    scrollLeftToValue(scrollLeft) {
      const min = Number(this.properties.min) || DEFAULT_MIN;
      const max = Number(this.properties.max) || DEFAULT_MAX;
      const maxIndex = Math.round((max - min) / STEP);
      const index = Math.max(0, Math.min(maxIndex, Math.round((Number(scrollLeft) || 0) / this.data.tickWidth)));
      return this.normalized(min + index * STEP);
    },

    prepare(value) {
      const windowWidth = this.windowWidth();
      const tickWidth = Math.max(8, Math.round(TICK_RPX * windowWidth / 750 * 10) / 10);
      const viewportWidth = Math.max(240, windowWidth - 60 * windowWidth / 750);
      const normalizedValue = this.normalized(value);
      this.currentScrollLeft = this.valueToScrollLeft(normalizedValue, tickWidth);
      this.setData({
        ticks: this.buildTicks(),
        displayValue: this.format(normalizedValue),
        rangeText: `${this.normalized(this.properties.min).toFixed(1)}–${this.normalized(this.properties.max).toFixed(1)} cm`,
        tickWidth,
        sidePadding: Math.max(0, Math.round((viewportWidth - tickWidth) / 2)),
        scrollLeft: this.currentScrollLeft
      });
    },

    onTouchStart() {
      this.interacting = true;
      clearTimeout(this.snapTimer);
    },

    onTouchEnd() {
      this.interacting = false;
      clearTimeout(this.snapTimer);
      this.snapTimer = setTimeout(() => this.snap(), 220);
    },

    onScroll(event) {
      const scrollLeft = Number(event.detail && event.detail.scrollLeft) || 0;
      this.currentScrollLeft = scrollLeft;
      const displayValue = this.format(this.scrollLeftToValue(scrollLeft));
      if (displayValue !== this.data.displayValue) this.setData({ displayValue });
      if (!this.interacting) {
        clearTimeout(this.snapTimer);
        this.snapTimer = setTimeout(() => this.snap(), 180);
      }
    },

    snap() {
      if (!this.properties.visible) return;
      const value = this.scrollLeftToValue(this.currentScrollLeft || this.data.scrollLeft);
      this.setData({
        displayValue: this.format(value),
        scrollLeft: this.valueToScrollLeft(value)
      });
    },

    confirm() {
      this.triggerEvent('confirm', { value: this.normalized(this.data.displayValue) });
    }
  }
});
