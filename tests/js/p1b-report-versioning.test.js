const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const cachePath = path.join(root, 'miniprogram/utils/reportCache.js');
const assessmentPath = path.join(root, 'miniprogram/pages/assessment/assessment.js');
const reportPath = path.join(root, 'miniprogram/pages/report/report.js');
const basisPath = path.join(root, 'miniprogram/pages/report-basis/report-basis.js');
const apiPath = path.join(root, 'miniprogram/utils/api.js');
const authPath = path.join(root, 'miniprogram/utils/auth.js');

function storageMock() {
  const values = new Map();
  return {
    values,
    wx: {
      setStorageSync(key, value) { values.set(key, value); },
      getStorageSync(key) { return values.get(key); },
      removeStorageSync(key) { values.delete(key); },
      getStorageInfoSync() { return { keys: [...values.keys()] }; }
    }
  };
}

test('versioned report cache is scoped by user, report id, and version', () => {
  const mock = storageMock();
  global.wx = mock.wx;
  delete require.cache[cachePath];
  const cache = require(cachePath);
  const reportV1 = { report_id: 'rpt-one', report_version: 1, title: 'v1' };
  const reportV2 = { report_id: 'rpt-two', report_version: 2, title: 'v2' };
  assert.equal(cache.saveReport('user-a', reportV1), true);
  assert.equal(cache.saveReport('user-a', reportV2), true);
  assert.equal(cache.loadReport('user-a', 'rpt-one', 1).title, 'v1');
  assert.equal(cache.loadReport('user-a', 'rpt-two', 2).title, 'v2');
  assert.equal(cache.loadReport('user-b', 'rpt-one', 1), null);
  assert.equal(cache.loadReport('user-a', 'rpt-one', 2), null);
  assert.deepEqual(cache.getActiveRef('user-a'), { reportId: 'rpt-two', reportVersion: 2 });
  cache.clearAllReportCaches();
  assert.equal([...mock.values.keys()].length, 0);
});

test('assessment creates one report idempotency key and reuses it for network retry', () => {
  const assessment = fs.readFileSync(assessmentPath, 'utf8');
  const api = fs.readFileSync(apiPath, 'utf8');
  assert.match(assessment, /createReportIdempotencyKey/);
  assert.match(assessment, /calculateEnergy\(payload, \{ idempotencyKey \}\)/);
  assert.match(assessment, /birth_time_unknown/);
  assert.match(assessment, /reportCache\.saveReport/);
  assert.match(assessment, /report_id=.*report_version/);
  assert.match(api, /return calculateEnergy\(payload, \{ \.\.\.options, idempotencyKey, networkRetried: true \}\)/);
});

test('report, basis, poster, and recommendation keep the explicit report version', () => {
  const report = fs.readFileSync(reportPath, 'utf8');
  const basis = fs.readFileSync(basisPath, 'utf8');
  assert.match(report, /getReport\(ref\.reportId, ref\.reportVersion/);
  assert.match(report, /getReportPoster/);
  assert.match(report, /posterRenderView = this\.buildPosterRenderView/);
  assert.match(report, /sanitizedPayloadHash: this\.posterPayloadHash/);
  assert.match(report, /createReportDIYRecommendation/);
  assert.match(report, /expected_report_version|currentReport\.report_version/);
  assert.match(report, /report-basis\/report-basis\?report_id=/);
  assert.match(basis, /getReportBasis/);
  assert.match(basis, /payload\.report_id !== this\.reportRef\.reportId/);
  assert.doesNotMatch(basis, /setStorageSync\([^\n]*input_snapshot/);
  assert.match(report, /this\.requestedReportRef \? null : wx\.getStorageSync\('energyReport'\)/);
  assert.match(report, /getReportBasis\(report\.report_id, report\.report_version/);
});

test('private report caches are cleared on logout and account recovery', () => {
  const auth = fs.readFileSync(authPath, 'utf8');
  assert.match(auth, /require\('\.\/reportCache'\)\.clearAllReportCaches\(\)/);
  assert.match(auth, /clearPrivateCaches\(\)/);
});
