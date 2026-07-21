const fs = require('fs')
const path = require('path')

const MAIN_PACKAGE_LIMIT_BYTES = 1_500_000
const projectRoot = path.resolve(__dirname, '..')
const miniprogramRoot = path.join(projectRoot, 'miniprogram')

function normalizeRelativePath(value) {
  return value.split(path.sep).join('/').replace(/^\.\//, '').replace(/\/$/, '')
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'))
}

function buildExclusions(appConfig, projectConfig) {
  const excludedFolders = new Set(['node_modules'])
  const excludedFiles = new Set()
  const packIgnores = projectConfig.packOptions?.ignore || []

  for (const rule of packIgnores) {
    const value = normalizeRelativePath(String(rule.value || ''))
    if (!value) continue

    if (rule.type === 'folder') {
      excludedFolders.add(value)
    } else if (rule.type === 'file') {
      excludedFiles.add(value)
    } else {
      throw new Error(`Unsupported project.config.json pack ignore type: ${rule.type}`)
    }
  }

  const subpackages = appConfig.subPackages || appConfig.subpackages || []
  for (const subpackage of subpackages) {
    const root = normalizeRelativePath(String(subpackage.root || ''))
    if (root) excludedFolders.add(root)
  }

  return { excludedFolders, excludedFiles }
}

function isExcluded(relativePath, exclusions) {
  const normalizedPath = normalizeRelativePath(relativePath)
  if (exclusions.excludedFiles.has(normalizedPath)) return true

  for (const folder of exclusions.excludedFolders) {
    if (normalizedPath === folder || normalizedPath.startsWith(`${folder}/`)) return true
  }
  return false
}

function collectMainPackageFiles(root, exclusions, relativeDirectory = '') {
  const directory = path.join(root, relativeDirectory)
  const files = []

  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const relativePath = normalizeRelativePath(path.join(relativeDirectory, entry.name))
    if (isExcluded(relativePath, exclusions)) continue

    if (entry.isDirectory()) {
      files.push(...collectMainPackageFiles(root, exclusions, relativePath))
    } else if (entry.isFile()) {
      files.push({
        path: relativePath,
        bytes: fs.statSync(path.join(root, relativePath)).size,
      })
    }
  }

  return files
}

function formatBytes(bytes) {
  return `${bytes.toLocaleString('en-US')} bytes (${(bytes / 1024 / 1024).toFixed(2)} MiB)`
}

function inspectMainPackage() {
  const appConfig = readJson(path.join(miniprogramRoot, 'app.json'))
  const projectConfig = readJson(path.join(miniprogramRoot, 'project.config.json'))
  const exclusions = buildExclusions(appConfig, projectConfig)
  const files = collectMainPackageFiles(miniprogramRoot, exclusions)
  const totalBytes = files.reduce((sum, file) => sum + file.bytes, 0)

  return {
    files,
    totalBytes,
    limitBytes: MAIN_PACKAGE_LIMIT_BYTES,
    remainingBytes: MAIN_PACKAGE_LIMIT_BYTES - totalBytes,
  }
}

function main() {
  const result = inspectMainPackage()
  console.log(
    `Mini-program main package source size: ${formatBytes(result.totalBytes)} / ${formatBytes(result.limitBytes)}`,
  )

  if (result.totalBytes <= result.limitBytes) {
    console.log(`Main package size gate passed; headroom: ${formatBytes(result.remainingBytes)}`)
    return
  }

  const largestFiles = [...result.files]
    .sort((left, right) => right.bytes - left.bytes)
    .slice(0, 10)
    .map((file) => `  ${formatBytes(file.bytes)}  ${file.path}`)
    .join('\n')

  console.error(`Main package exceeds the 1.5 MB source budget by ${formatBytes(-result.remainingBytes)}.`)
  console.error(`Largest included files:\n${largestFiles}`)
  process.exitCode = 1
}

if (require.main === module) main()

module.exports = {
  MAIN_PACKAGE_LIMIT_BYTES,
  buildExclusions,
  collectMainPackageFiles,
  inspectMainPackage,
  isExcluded,
}
