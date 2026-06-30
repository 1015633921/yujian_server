const { assetUrl } = require('../../utils/assets');

const CRYSTAL_ASSETS = [
  assetUrl('home/aquamarine.webp'),
  assetUrl('home/clear-quartz.webp'),
  assetUrl('home/moonstone.webp'),
  assetUrl('home/citrine.webp'),
  assetUrl('home/amethyst.webp')
];

const KNOWLEDGE_LAYERS = [
  {
    index: '01',
    title: '规则库',
    subtitle: '先把推荐逻辑说清楚',
    accent: '#647C70',
    desc: '五行、喜用、愿望、MBTI、七脉轮和直觉色彩都会被拆成可配置的规则。它们不是一句玄乎的结论，而是能影响权重、颜色、材料排序和解释文案的线索。',
    points: ['权重可追溯', '选项可配置', '结果可解释']
  },
  {
    index: '02',
    title: '材料库',
    subtitle: '真正的壁垒在珠子知识',
    accent: '#365C9C',
    desc: '每种水晶不只记录名字和价格，还要记录五行、颜色、脉轮、适用场景、质感表现、珠径效果、搭配限制和实拍素材。推荐能不能可信，最终要落在材料库够不够深。',
    points: ['水晶标签', '珠径表现', '实拍成串']
  },
  {
    index: '03',
    title: '解释库',
    subtitle: '让小白也知道为什么',
    accent: '#C6A15B',
    desc: '用户看到的不是公式，而是一段能听懂的话：为什么选这个主石，为什么用这组颜色，为什么此刻更适合柔和、稳定或行动感。',
    points: ['推荐原因', '边界提醒', '温柔表达']
  }
];

const SIGNALS = [
  {
    key: 'wuxing',
    index: '五行',
    title: '长期底色',
    accent: '#647C70',
    desc: '根据出生日期、时间和出生地校准真太阳时，再生成四柱信息。它提供长期结构参考，不是简单地“缺什么就补什么”。',
    use: '影响主调元素、喜用方向和整体调和策略。',
    tags: ['文化框架', '真太阳时', '整体强弱']
  },
  {
    key: 'wish',
    index: '愿望',
    title: '这次佩戴目的',
    accent: '#C83B3D',
    desc: '睡眠、专注、关系、行动、守护等愿望会让推荐从“适合你这个人”进一步靠近“适合这一次”。',
    use: '影响主石角色、配珠方向和报告里的行动建议。',
    tags: ['用户主动选择', '场景目标', '可快速理解']
  },
  {
    key: 'mbti',
    index: 'MBTI',
    title: '性格偏好',
    accent: '#365C9C',
    desc: 'MBTI 只作为偏好语言，不用来给人定型。它帮助我们理解用户更偏外放、秩序、共情、探索还是克制。',
    use: '影响配色接受度、方案气质和文案语气。',
    tags: ['可选', '偏好辅助', '中性兜底']
  },
  {
    key: 'chakra',
    index: '脉轮',
    title: '近期状态',
    accent: '#8B82B3',
    desc: '七脉轮来自瑜伽与身心觉察传统。我们只把它作为近期状态语言，例如表达受阻、想更稳定、想更有行动力。',
    use: '影响动态能量、颜色家族和材料排序。',
    tags: ['状态觉察', '非医疗诊断', '轻量选择']
  },
  {
    key: 'mood',
    index: '色彩',
    title: '第一眼直觉',
    accent: '#F2B51D',
    desc: '色彩不是诊断，但能反映当下被哪种视觉气质吸引。它让方案更像“现在的你”，而不只是长期底色。',
    use: '影响视觉标签、辅助珠和整体配色。',
    tags: ['审美线索', '当下偏好', '不做绝对判断']
  }
];

const FLOW_STEPS = [
  {
    title: '先建档',
    desc: '把出生信息、愿望和可选偏好整理成一份能量档案。'
  },
  {
    title: '再匹配',
    desc: '用规则库计算方向，用材料库筛选真实可用的水晶。'
  },
  {
    title: '最后解释',
    desc: '把选择主石、配珠、颜色和场景的原因讲给用户听。'
  }
];

const BOUNDARIES = [
  {
    title: '不做医学判断',
    desc: '七脉轮、色彩和水晶推荐只用于文化体验、身心觉察和审美定制。身体不适仍应以专业医疗建议为准。'
  },
  {
    title: '不把人格定死',
    desc: 'MBTI 是偏好语言，不是身份标签。用户不填写也能继续，系统会用中性权重处理。'
  },
  {
    title: '不靠随机抽签',
    desc: '每个维度都会进入明确规则，推荐结果要能说明“为什么是这颗珠子”。'
  }
];

const MATERIAL_FIELDS = [
  '五行属性',
  '颜色家族',
  '脉轮映射',
  '情绪场景',
  '珠径效果',
  '实拍素材',
  '搭配限制',
  '价格区间'
];

Page({
  data: {
    crystals: CRYSTAL_ASSETS.map((src, index) => ({
      src,
      style: `transform: rotate(${index * 72}deg) translateY(-78rpx) rotate(${-index * 72}deg);`
    })),
    knowledgeLayers: KNOWLEDGE_LAYERS,
    signals: SIGNALS,
    flowSteps: FLOW_STEPS,
    boundaries: BOUNDARIES,
    materialFields: MATERIAL_FIELDS
  },

  goBack() {
    if (getCurrentPages().length > 1) {
      wx.navigateBack();
      return;
    }
    wx.switchTab({ url: '/pages/home/home' });
  },

  startAssessment() {
    wx.setStorageSync('customMode', {
      id: 'wuxing',
      title: '五行定制',
      selectedAt: Date.now()
    });
    wx.switchTab({ url: '/pages/assessment/assessment' });
  },

  openWorkspace() {
    wx.switchTab({ url: '/pages/workspace/workspace' });
  },

  onShareAppMessage() {
    return {
      title: '宇涧能量档案是怎么来的',
      path: '/pages/assessment-guide/assessment-guide'
    };
  }
});
