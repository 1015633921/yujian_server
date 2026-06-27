const posts = [
  {
    id: 'ocean',
    title: '温柔治愈系',
    author: '宇涧灵感室',
    desc: '柔和配色 · 平衡情绪，用月光石、海蓝宝与白水晶做出清透安静的日常手串。',
    story: '这条方案来自清晨光线下的柔雾感搭配。海蓝宝负责清爽表达，月光石让情绪更柔和，白水晶作为底色让整条手串更通透。',
    scene: '适合睡前复盘、沟通前稳定情绪、通勤或第一次尝试水晶手串的用户。',
    authorNote: '如果希望更温柔，可以提高月光石比例；如果希望更清爽，可以增加海蓝宝和白水晶。',
    likes: 1208,
    tone: 'blue',
    recipe: ['aquamarine', 'moonstone', 'clearQuartz', 'silverSpacer'],
    materials: ['海蓝宝', '月光石', '白水晶', '银色隔珠'],
    tags: ['情绪平衡', '清透', '日常']
  },
  {
    id: 'summer',
    title: '夏日清凉系',
    author: '宇涧选品',
    desc: '蓝白配色 · 清爽能量，适合想要干净、轻盈、不压手的夏季搭配。',
    story: '蓝白色系会让视觉重量变轻，搭配小尺寸珠径更适合日常佩戴。整体强调清爽、松弛和一点点明亮感。',
    scene: '适合夏日通勤、旅行、浅色穿搭，以及偏爱低存在感饰品的人。',
    authorNote: '可以用少量金色隔珠提升精致度，但不要太多，避免破坏清爽感。',
    likes: 938,
    tone: 'clear',
    recipe: ['clearQuartz', 'aquamarine', 'moonstone', 'goldSpacer'],
    materials: ['白水晶', '海蓝宝', '月光石', '金色隔珠'],
    tags: ['夏日', '清爽', '通勤']
  },
  {
    id: 'wealth',
    title: '行动力黄水晶',
    author: '宇涧灵感室',
    desc: '黄水晶与虎眼石组合，适合面试、考试、项目启动等需要行动力的场景。',
    story: '这条更偏明亮的行动能量。黄水晶给目标感，虎眼石给执行力，白水晶把节奏拉稳。',
    scene: '适合面试、考试周、项目启动、需要把计划拆成行动的阶段。',
    authorNote: '黄水晶不必铺太满，中间穿插白水晶会更耐看。',
    likes: 860,
    tone: 'gold',
    recipe: ['citrine', 'tigerEye', 'clearQuartz', 'goldSpacer'],
    materials: ['黄水晶', '虎眼石', '白水晶', '金色隔珠'],
    tags: ['事业', '行动力', '目标感']
  },
  {
    id: 'love',
    title: '粉晶礼物款',
    author: '宇涧搭配师',
    desc: '柔和粉白色系，适合生日礼物、闺蜜礼和日常温柔穿搭。',
    story: '粉晶负责柔和的人际氛围，月光石让颜色更细腻，少量金色配件增加礼物感。',
    scene: '适合生日礼物、闺蜜礼、约会、想提升亲和感的日常穿搭。',
    authorNote: '不想太甜时，可以减少粉晶比例，加入更多月光石。',
    likes: 780,
    tone: 'pink',
    recipe: ['roseQuartz', 'moonstone', 'clearQuartz', 'goldSpacer'],
    materials: ['粉晶', '月光石', '白水晶', '金色隔珠'],
    tags: ['礼物', '温柔', '人缘']
  },
  {
    id: 'black',
    title: '黑曜石通勤守护',
    author: '宇涧选品',
    desc: '黑曜石搭配白水晶，适合通勤、高压沟通和偏简洁的穿搭。',
    story: '黑曜石是很直接的守护型能量，加入白水晶可以让整体不那么沉，日常更好搭配。',
    scene: '适合通勤、会议、高压沟通、需要减少外界干扰的时候。',
    authorNote: '黑曜石不建议做得过满，留一点清透珠子会更好戴。',
    likes: 692,
    tone: 'black',
    recipe: ['obsidian', 'clearQuartz', 'silverSpacer'],
    materials: ['黑曜石', '白水晶', '银色隔珠'],
    tags: ['守护', '通勤', '边界感']
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
