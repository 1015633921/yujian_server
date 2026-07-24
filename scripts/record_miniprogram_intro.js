const fs = require('node:fs');
const path = require('node:path');

const automator = require(process.env.YUJIAN_AUTOMATOR_MODULE);

const root = path.resolve(__dirname, '..');
const projectPath = path.join(root, 'miniprogram');
const outputDir = path.join(root, 'output', 'intro-video', 'captures');
const cliPath = '/Applications/wechatwebdevtools.app/Contents/MacOS/cli';

fs.mkdirSync(outputDir, { recursive: true });

const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

async function capture(miniProgram, name) {
  const file = path.join(outputDir, `${name}.png`);
  await miniProgram.screenshot({ path: file });
  console.log(`[capture] ${file}`);
  await wait(900);
  return file;
}

async function waitForRoute(miniProgram, expected, timeout = 30000) {
  const endAt = Date.now() + timeout;
  while (Date.now() < endAt) {
    const page = await miniProgram.currentPage();
    if (page && page.path === expected) return page;
    await wait(350);
  }
  const page = await miniProgram.currentPage();
  throw new Error(`Expected route ${expected}, got ${page && page.path}`);
}

(async () => {
  const miniProgram = await automator.launch({
    cliPath,
    projectPath,
    trustProject: true,
    timeout: 60000,
  });

  try {
    let page = await miniProgram.reLaunch('/pages/home/home');
    await page.waitFor(1200);
    await capture(miniProgram, '01-home');

    page = await miniProgram.switchTab('/pages/assessment/assessment');
    await page.waitFor(800);
    const assessmentData = await page.data();
    const wish = (assessmentData.wishOptions || [])[0] || {};
    const mbti = (assessmentData.mbtiOptions || [])[0] || {};
    const state = (assessmentData.chakraOptions || [])[0] || {};
    const palette = (assessmentData.moodPalettes || [])[0] || {};
    await page.setData({
      'form.name': '演示用户',
      'form.gender': 'female',
      'form.birthDate': '1995-06-15',
      'form.birthTime': '09:30',
      'form.birthTimeUnknown': false,
      'form.birthRegion': ['上海市', '上海市'],
      'form.birthPlace': '上海市',
    });
    await page.callMethod('refreshOptionState');
    await capture(miniProgram, '02-assessment-basic');

    await page.callMethod('goToStep', 1);
    await page.setData({ 'form.wishes': [wish.value || wish.id].filter(Boolean) });
    await page.callMethod('refreshOptionState');
    await capture(miniProgram, '03-assessment-goal');

    await page.callMethod('goToStep', 2);
    await page.setData({ 'form.mbti': mbti.value || mbti.id || '' });
    await page.callMethod('refreshOptionState');
    await page.callMethod('goToStep', 3);
    await page.setData({ 'form.chakraAnswers': [state.value || state.id].filter(Boolean) });
    await page.callMethod('refreshOptionState');
    await page.callMethod('goToStep', 4);
    await page.setData({ 'form.moodPaletteId': palette.value || palette.id || '' });
    await page.callMethod('refreshOptionState');
    await page.callMethod('goToStep', 5);
    await capture(miniProgram, '04-assessment-review');

    // This invokes the same final in-app action as the review page's button.
    // It only creates a test-environment report for the local demo user.
    await page.callMethod('startAssessment');
    page = await waitForRoute(miniProgram, 'pages/report/report');
    await page.waitFor(1400);
    await capture(miniProgram, '05-assessment-report');

    await page.callMethod('openWristModal');
    await wait(500);
    await capture(miniProgram, '06-report-wrist');
    await page.setData({ wristRulerValue: '16.0' });
    await page.callMethod('confirmWristAndRecommend');
    page = await waitForRoute(miniProgram, 'pages/workspace/workspace');
    await page.waitFor(1800);
    await capture(miniProgram, '07-diy-recommendation');

    const cards = await page.$$('.material-card');
    for (const card of cards.slice(0, 3)) {
      await card.tap();
      await wait(650);
    }
    await capture(miniProgram, '08-diy-add-materials');

    await page.callMethod('startStringingPhysics');
    await wait(1800);
    await capture(miniProgram, '09-diy-stringed');

    console.log(JSON.stringify({ outputDir, status: 'ok' }));
  } finally {
    await miniProgram.close();
  }
})().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
