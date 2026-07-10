const automator = require('./miniprogram-automator-tmp/node_modules/miniprogram-automator');

(async () => {
  const mp = await automator.connect({ wsEndpoint: 'ws://127.0.0.1:9420' });
  const page = await mp.reLaunch('/pages/community-detail/community-detail?id=morning-clear-quartz');
  await page.waitFor(2500);
  const button = await page.$('.primary-button');
  if (button) {
    await button.tap();
    await page.waitFor(4500);
  }
  const current = await mp.currentPage();
  console.log('current', current.path);
  await mp.screenshot({ path: '.codex/acceptance-shots/community-to-diy.png' });
  mp.disconnect();
})().catch(error => {
  console.error(error);
  process.exit(1);
});
