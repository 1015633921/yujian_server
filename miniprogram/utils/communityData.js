const posts = [
  {
    id: 'ocean',
    title: '海蓝宝治愈配方',
    author: '小宁的能量盒',
    desc: '给最近睡眠浅、表达卡住的人。主石海蓝宝，搭配月光石和白水晶。',
    story: '这条手串的灵感来自海边散步后的松弛感。海蓝宝负责把紧绷的表达慢慢打开，月光石把夜里的情绪放柔，白水晶则像一层清透的底光，让整条串不显沉重。',
    scene: '适合睡前复盘、沟通前稳定情绪、需要温柔表达的工作日。',
    authorNote: '我会把海蓝宝放在视觉中心，旁边用月光石过渡，佩戴起来更像一口慢慢呼出去的气。',
    likes: 1280,
    tone: 'blue',
    recipe: ['aquamarine', 'aquamarine', 'moonstone', 'clearQuartz', 'silverSpacer'],
    materials: ['海蓝宝', '月光石', '白水晶', '银色隔珠'],
    tags: ['情绪平衡', '表达力', '睡眠放松']
  },
  {
    id: 'wealth',
    title: '黄水晶行动力手串',
    author: '祥意工作室',
    desc: '适合考试、面试、项目启动。黄水晶和虎眼石负责把计划落地。',
    story: '这条更偏明亮的行动能量。黄水晶给目标感，虎眼石给执行力，白水晶把节奏拉稳，适合那些已经想清楚方向但迟迟没有开始的人。',
    scene: '适合面试、考试周、项目启动、需要把计划拆成行动的阶段。',
    authorNote: '我喜欢把虎眼石穿插在黄水晶之间，让整条串既有财气，也不会显得太飘。',
    likes: 960,
    tone: 'gold',
    recipe: ['citrine', 'tigerEye', 'citrine', 'clearQuartz', 'goldSpacer'],
    materials: ['黄水晶', '虎眼石', '白水晶', '金色隔珠'],
    tags: ['事业财富', '行动力', '目标感']
  },
  {
    id: 'love',
    title: '粉晶狐狸礼物款',
    author: '莓莓',
    desc: '情侣、闺蜜都适合，柔和不甜腻，可以直接生成心愿单。',
    story: '粉晶负责温柔的人际磁场，月光石让情绪更细腻，狐狸吊坠给这条串一点灵动的小心思。它不是浓烈的甜，而是日常也能戴的柔软感。',
    scene: '适合生日礼物、闺蜜礼、约会、想提升亲和力的日常穿搭。',
    authorNote: '如果不想太甜，可以减少粉晶比例，把月光石加多一点，整体会更清透。',
    likes: 2140,
    tone: 'pink',
    recipe: ['roseQuartz', 'roseQuartz', 'moonstone', 'foxPendant', 'goldSpacer'],
    materials: ['粉晶', '月光石', '狐狸吊坠', '金色隔珠'],
    tags: ['爱情人缘', '礼物款', '温柔感']
  },
  {
    id: 'clear',
    title: '白水晶净化叠戴',
    author: '素色',
    desc: '通勤、学习、冥想都能戴的清透款，用白水晶做日常能量底盘。',
    story: '白水晶的好处是干净、百搭、不会过度抢戏。它适合做叠戴里的底层能量，把杂乱的状态慢慢理顺。',
    scene: '适合通勤、学习、冥想、第一次尝试水晶手串的新手。',
    authorNote: '白水晶可以和几乎所有主石叠戴，建议先从 8mm 开始。',
    likes: 860,
    tone: 'clear',
    recipe: ['clearQuartz', 'clearQuartz', 'moonstone', 'silverSpacer'],
    materials: ['白水晶', '月光石', '银色隔珠'],
    tags: ['净化', '新手友好', '百搭']
  },
  {
    id: 'black',
    title: '黑曜石守护通勤串',
    author: '曜石',
    desc: '适合通勤和高压场景，稳住边界感，也让穿搭更利落。',
    story: '黑曜石是很直接的守护型能量，适合需要保持边界和专注的人。加一点白水晶可以让整体不那么沉。',
    scene: '适合通勤、会议、高压沟通、需要减少外界干扰的时候。',
    authorNote: '黑曜石不要做得太满，留一点清透珠子，日常会更好戴。',
    likes: 740,
    tone: 'black',
    recipe: ['obsidian', 'obsidian', 'clearQuartz', 'silverSpacer'],
    materials: ['黑曜石', '白水晶', '银色隔珠'],
    tags: ['守护辟邪', '边界感', '通勤']
  }
];

function getCommunityPosts() {
  return posts;
}

function getCommunityPost(id) {
  return posts.find(item => item.id === id) || posts[0];
}

module.exports = {
  getCommunityPosts,
  getCommunityPost
};
