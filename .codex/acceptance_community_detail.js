const automator = require('./miniprogram-automator-tmp/node_modules/miniprogram-automator');

(async () => {
  const mp = await automator.connect({ wsEndpoint: 'ws://127.0.0.1:9420' });
  const page = await mp.reLaunch('/pages/community/community');
  await page.waitFor(2500);
  const card = await page.$('.post-card');
  if (card) {
    await card.tap();
    await page.waitFor(2500);
  }
  const current = await mp.currentPage();
  console.log('current', current.path);
  await mp.screenshot({ path: '.codex/acceptance-shots/community-detail.png' });
  mp.disconnect();
})().catch(error => {
  console.error(error);
  process.exit(1);
});
