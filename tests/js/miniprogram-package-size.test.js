const assert = require('node:assert/strict')
const test = require('node:test')

const {
  MAIN_PACKAGE_LIMIT_BYTES,
  buildExclusions,
  inspectMainPackage,
  isExcluded,
} = require('../../scripts/check_miniprogram_package_size')

test('package exclusions include project ignores and subpackage roots', () => {
  const exclusions = buildExclusions(
    {
      subPackages: [{ root: 'pages-commerce', pages: ['checkout/checkout'] }],
    },
    {
      packOptions: {
        ignore: [
          { type: 'folder', value: 'assets' },
          { type: 'file', value: 'pages/test.html' },
        ],
      },
    },
  )

  assert.equal(isExcluded('assets/sounds/collision.mp3', exclusions), true)
  assert.equal(isExcluded('pages/test.html', exclusions), true)
  assert.equal(isExcluded('pages-commerce/checkout/checkout.js', exclusions), true)
  assert.equal(isExcluded('pages/workspace/workspace.js', exclusions), false)
})

test('current mini-program main package stays within the 1.5 MB source budget', () => {
  const result = inspectMainPackage()

  assert.equal(result.limitBytes, MAIN_PACKAGE_LIMIT_BYTES)
  assert.ok(
    result.totalBytes <= MAIN_PACKAGE_LIMIT_BYTES,
    `main package source size ${result.totalBytes} exceeds ${MAIN_PACKAGE_LIMIT_BYTES}`,
  )
})
