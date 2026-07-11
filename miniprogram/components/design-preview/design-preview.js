const { buildDesignPreviewBeads } = require('../../utils/designPreview');

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
    renderBeads: []
  },

  observers: {
    'sequence, placements, design': function updatePreview(sequence, placements, design) {
      this.setData({
        renderBeads: buildDesignPreviewBeads(sequence || [], placements || [], design || {})
      });
    }
  },

  methods: {
    onTrayImageError() {
      this.triggerEvent('trayerror');
    }
  }
});
