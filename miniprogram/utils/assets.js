const env = require('../config/env');

const ASSET_BASE_URL = String(env.assetBaseUrl || env.testAssetBaseUrl || '').replace(/\/$/, '');

function assetUrl(path) {
  const cleanPath = String(path || '')
    .replace(/^\/+/, '')
    .replace(/^assets\//, '');
  if (!cleanPath) return ASSET_BASE_URL;
  return `${ASSET_BASE_URL}/${cleanPath}`;
}

module.exports = {
  ASSET_BASE_URL,
  assetUrl
};
