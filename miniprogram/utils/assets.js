const env = require('../config/env');
const manifest = require('../config/asset-manifest');

const ASSET_BASE_URL = String(env.assetBaseUrl || '').replace(/\/$/, '');
const ASSET_OBJECTS = manifest && manifest.assets ? manifest.assets : {};

function assetUrl(path) {
  const cleanPath = String(path || '')
    .replace(/^\/+/, '')
    .replace(/^assets\//, '');
  if (!cleanPath) return ASSET_BASE_URL;
  const entry = ASSET_OBJECTS[cleanPath];
  const objectPath = entry && entry.object ? entry.object : cleanPath;
  return `${ASSET_BASE_URL}/${String(objectPath).replace(/^\/+/, '')}`;
}

module.exports = {
  ASSET_BASE_URL,
  assetUrl
};
