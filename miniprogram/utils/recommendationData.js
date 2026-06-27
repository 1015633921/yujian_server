const recommendations = [
  {
    id: 'moonlight-sleep',
    name: '月光石轻眠',
    subtitle: '睡前放松与情绪整理',
    desc: '用清透、低刺激的配色，把睡前紧绷感慢慢放下来。',
    price: 268,
    tone: 'blue',
    recipe: ['moonstone', 'clearQuartz', 'aquamarine'],
    materials: [
      { name: '月光石', role: '主石', reason: '柔化情绪起伏，让整条手串保持温润安静。' },
      { name: '白水晶', role: '过渡石', reason: '增加通透感，也让不同颜色之间衔接得更自然。' },
      { name: '海蓝宝', role: '点睛石', reason: '加入轻微的冷蓝色，帮助视觉和心理节奏一起放慢。' }
    ],
    designStory: '这套方案不是追求强烈的“助眠符号”，而是模拟月光落在水面上的层次。珠子从柔白到浅蓝渐变，视觉刺激较低，适合在一天结束时佩戴。',
    designReason: '月光石占据主要视觉比例，白水晶负责留白，海蓝宝只做少量点缀。这样既保留安静感，也不会因为颜色过于单一而显得沉闷。',
    scenes: ['睡前阅读', '情绪紧绷时', '温柔通勤', '送给需要休息的人'],
    tags: ['轻眠', '舒缓', '清透']
  },
  {
    id: 'citrine-action',
    name: '黄水晶进阶',
    subtitle: '事业行动力与目标推进',
    desc: '明亮但不浮躁，用暖金色建立目标感，再用深色纹理稳住节奏。',
    price: 328,
    tone: 'gold',
    recipe: ['citrine', 'tigerEye', 'clearQuartz'],
    materials: [
      { name: '黄水晶', role: '主石', reason: '形成明亮的视觉中心，强调目标、信心与启动感。' },
      { name: '虎眼石', role: '稳定石', reason: '深浅纹理压住黄水晶的跳跃感，让方案更有执行力。' },
      { name: '白水晶', role: '调和石', reason: '在暖色之间加入呼吸空间，避免整条手串显得厚重。' }
    ],
    designStory: '它像一套为“开始行动”准备的配色：黄水晶负责点亮方向，虎眼石负责把脚踩在地上，白水晶则让思路保持清晰。',
    designReason: '黄水晶和虎眼石交替出现，比全部使用黄水晶更稳重。少量白水晶形成节奏断点，让商务与日常场景都容易佩戴。',
    scenes: ['面试与汇报', '项目启动', '考试备考', '需要推进计划时'],
    tags: ['事业', '行动力', '目标感']
  },
  {
    id: 'amethyst-focus',
    name: '紫水晶灵感',
    subtitle: '创作专注与思绪整理',
    desc: '以紫色为情绪锚点，用透明和柔白平衡神秘感与日常感。',
    price: 298,
    tone: 'violet',
    recipe: ['amethyst', 'clearQuartz', 'moonstone'],
    materials: [
      { name: '紫水晶', role: '主石', reason: '建立鲜明的灵感主题，适合需要沉浸与专注的状态。' },
      { name: '白水晶', role: '提亮石', reason: '减少大面积紫色的压迫感，让视觉更清晰。' },
      { name: '月光石', role: '柔化石', reason: '把紫水晶的浓度过渡得更温柔，提升日常佩戴性。' }
    ],
    designStory: '这套设计来自夜晚书桌上的光影。紫水晶像深色背景，白水晶和月光石像落在纸面上的光，让注意力集中但不紧绷。',
    designReason: '紫水晶不连续堆叠，而是被白水晶和月光石分隔，形成有停顿的节奏。既保留主题色，也更适合长时间佩戴。',
    scenes: ['写作与绘画', '深度工作', '冥想复盘', '需要整理思路时'],
    tags: ['灵感', '专注', '创作']
  }
];

function getRecommendations() {
  return recommendations;
}

function getRecommendation(id) {
  return recommendations.find(item => item.id === id) || recommendations[0];
}

module.exports = {
  getRecommendations,
  getRecommendation
};
