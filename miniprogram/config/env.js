// Stable entrypoint. The ignored env.current.js is generated when an
// environment is selected; a fresh checkout safely defaults to test.
try {
  module.exports = require('./env.current');
} catch (_error) {
  module.exports = require('./env.test');
}
