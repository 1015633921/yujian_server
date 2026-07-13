const {
  buildDesignPreviewBeads,
  buildDesignPreviewGuide
} = require('../../utils/designPreview');

Component({
  properties: {
    trayImage: { type: String, value: '' },
    trayTheme: { type: String, value: 'white' },
    trayFailed: { type: Boolean, value: false },
    sequence: { type: Array, value: [] },
    placements: { type: Array, value: [] },
    design: { type: Object, value: null }
  },

  data: {
    renderBeads: [],
    showGuide: false,
    guideStyle: ''
  },

  observers: {
    'sequence, placements, design': function updatePreview(sequence, placements, design) {
      const renderBeads = buildDesignPreviewBeads(sequence || [], placements || [], design || {});
      const guide = buildDesignPreviewGuide(renderBeads, design || {});
      this.setData({
        renderBeads,
        showGuide: guide.visible,
        guideStyle: guide.style
      });
    }
  },

  methods: {
    onTrayImageError() {
      this.triggerEvent('trayerror');
    }
  }
});
