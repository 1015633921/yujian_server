const fs = require('fs');
const path = require('path');
const automator = require('./miniprogram-automator-tmp/node_modules/miniprogram-automator');

(async () => {
  const outDir = path.resolve('.codex/acceptance-shots');
  fs.mkdirSync(outDir, { recursive: true });
  const mp = await automator.connect({ wsEndpoint: 'ws://127.0.0.1:9420' });
  const pages = [
    ['home', '/pages/home/home'],
    ['custom-mode', '/pages/custom-mode/custom-mode'],
    ['assessment-guide', '/pages/assessment-guide/assessment-guide'],
    ['assessment', '/pages/assessment/assessment'],
    ['report', '/pages/report/report'],
    ['workspace', '/pages/workspace/workspace'],
    ['community', '/pages/community/community'],
    ['search', '/pages/search/search'],
    ['cart', '/pages/inspiration-cart/inspiration-cart'],
    ['profile', '/pages/profile/profile'],
    ['my-plans', '/pages/my-plans/my-plans'],
    ['favorites', '/pages/community-favorites/community-favorites'],
    ['order-list', '/pages/order-list/order-list'],
    ['daily-energy', '/pages/daily-energy/daily-energy']
  ];
  const results = [];
  for (const [name, url] of pages) {
    try {
      await mp.reLaunch(url);
      await new Promise(resolve => setTimeout(resolve, 2500));
      const page = await mp.currentPage();
      const shot = path.join(outDir, `${name}.png`);
      await mp.screenshot({ path: shot });
      results.push({ name, url, current: page.path, shot });
    } catch (error) {
      results.push({ name, url, error: String(error.message || error) });
    }
  }
  mp.disconnect();
  console.log(JSON.stringify(results, null, 2));
})().catch(error => {
  console.error(error);
  process.exit(1);
});
