const REPORT_CACHE_PREFIX = 'reportSnapshot:';
const ACTIVE_REPORT_PREFIX = 'activeReportRef:';

function safeText(value) {
  return value === null || value === undefined ? '' : String(value).trim();
}

function identity(report = {}) {
  const reportId = safeText(report.report_id || report.reportId);
  const reportVersion = Number(report.report_version || report.reportVersion);
  if (!reportId || !Number.isInteger(reportVersion) || reportVersion < 1) return null;
  return { reportId, reportVersion };
}

function reportKey(userId, reportId, reportVersion) {
  return `${REPORT_CACHE_PREFIX}${safeText(userId)}:${safeText(reportId)}:v${Number(reportVersion)}`;
}

function activeKey(userId) {
  return `${ACTIVE_REPORT_PREFIX}${safeText(userId)}`;
}

function saveReport(userId, report) {
  const ref = identity(report);
  if (!safeText(userId) || !ref) return false;
  wx.setStorageSync(reportKey(userId, ref.reportId, ref.reportVersion), {
    userId: safeText(userId),
    reportId: ref.reportId,
    reportVersion: ref.reportVersion,
    report
  });
  wx.setStorageSync(activeKey(userId), ref);
  return true;
}

function loadReport(userId, reportId, reportVersion) {
  const envelope = wx.getStorageSync(reportKey(userId, reportId, reportVersion)) || {};
  if (safeText(envelope.userId) !== safeText(userId)) return null;
  if (safeText(envelope.reportId) !== safeText(reportId)) return null;
  if (Number(envelope.reportVersion) !== Number(reportVersion)) return null;
  return envelope.report || null;
}

function getActiveRef(userId) {
  const ref = wx.getStorageSync(activeKey(userId)) || {};
  const reportId = safeText(ref.reportId);
  const reportVersion = Number(ref.reportVersion);
  return reportId && Number.isInteger(reportVersion) && reportVersion > 0
    ? { reportId, reportVersion }
    : null;
}

function loadActiveReport(userId) {
  const ref = getActiveRef(userId);
  return ref ? loadReport(userId, ref.reportId, ref.reportVersion) : null;
}

function removeReport(userId, reportId, reportVersion) {
  wx.removeStorageSync(reportKey(userId, reportId, reportVersion));
  const active = getActiveRef(userId);
  if (active && active.reportId === reportId && active.reportVersion === Number(reportVersion)) {
    wx.removeStorageSync(activeKey(userId));
  }
}

function clearAllReportCaches() {
  let keys = [];
  try {
    keys = (wx.getStorageInfoSync && wx.getStorageInfoSync().keys) || [];
  } catch (error) {
    keys = [];
  }
  keys
    .filter(key => key.indexOf(REPORT_CACHE_PREFIX) === 0 || key.indexOf(ACTIVE_REPORT_PREFIX) === 0)
    .forEach(key => wx.removeStorageSync(key));
}

module.exports = {
  identity,
  saveReport,
  loadReport,
  getActiveRef,
  loadActiveReport,
  removeReport,
  clearAllReportCaches
};
