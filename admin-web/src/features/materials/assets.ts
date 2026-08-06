export const MATERIAL_ASSET_OUTPUT_SIZE = 512
export const MATERIAL_ASSET_TARGET_FILL = 0.985
export const MATERIAL_ASSET_MAX_COUNT = 24
export const MATERIAL_ASSET_MAX_SOURCE_BYTES = 12 * 1024 * 1024
export const MATERIAL_ASSET_MAX_SOURCE_PIXELS = 30_000_000
export const MATERIAL_ASSET_MAX_OUTPUT_BYTES = 800_000

export interface AlphaBounds {
  left: number
  top: number
  right: number
  bottom: number
  width: number
  height: number
  transparentPixels: number
}

export interface AssetMetrics {
  fillRatio: number
  offsetX: number
  offsetY: number
}

export interface ProcessedMaterialAsset {
  blob: Blob
  previewUrl: string
  sourceWidth: number
  sourceHeight: number
  metrics: AssetMetrics
}

export function materialAssetAlphaBounds(rgba: Uint8ClampedArray, width: number, height: number, threshold = 8): AlphaBounds | null {
  if (width <= 0 || height <= 0 || rgba.length < width * height * 4) return null
  let left = width
  let top = height
  let right = -1
  let bottom = -1
  let transparentPixels = 0
  for (let pixel = 0, index = 0; pixel < width * height; pixel += 1, index += 4) {
    const alpha = rgba[index + 3] || 0
    if (alpha < 250) transparentPixels += 1
    if (alpha <= threshold) continue
    const x = pixel % width
    const y = Math.floor(pixel / width)
    left = Math.min(left, x)
    right = Math.max(right, x)
    top = Math.min(top, y)
    bottom = Math.max(bottom, y)
  }
  if (right < left || bottom < top) return null
  return { left, top, right, bottom, width: right - left + 1, height: bottom - top + 1, transparentPixels }
}

export function materialAssetPlacement(bounds: Pick<AlphaBounds, 'width' | 'height'>): { x: number; y: number; width: number; height: number } {
  if (bounds.width <= 0 || bounds.height <= 0) throw new Error('未检测到有效主体')
  const targetExtent = Math.max(1, Math.floor(MATERIAL_ASSET_OUTPUT_SIZE * MATERIAL_ASSET_TARGET_FILL))
  const scale = Math.min(targetExtent / bounds.width, targetExtent / bounds.height)
  const width = Math.max(1, Math.round(bounds.width * scale))
  const height = Math.max(1, Math.round(bounds.height * scale))
  return {
    x: Math.round((MATERIAL_ASSET_OUTPUT_SIZE - width) / 2),
    y: Math.round((MATERIAL_ASSET_OUTPUT_SIZE - height) / 2),
    width,
    height,
  }
}

export function materialAssetMetrics(bounds: Pick<AlphaBounds, 'left' | 'right' | 'top' | 'bottom' | 'width' | 'height'> | null): AssetMetrics {
  if (!bounds) return { fillRatio: 0, offsetX: 0, offsetY: 0 }
  return {
    fillRatio: Math.max(bounds.width, bounds.height) / MATERIAL_ASSET_OUTPUT_SIZE,
    offsetX: (bounds.left + bounds.right + 1) / 2 - MATERIAL_ASSET_OUTPUT_SIZE / 2,
    offsetY: (bounds.top + bounds.bottom + 1) / 2 - MATERIAL_ASSET_OUTPUT_SIZE / 2,
  }
}

function acceptedMaterialAsset(file: File): boolean {
  const extension = file.name.split('.').pop()?.toLowerCase() || ''
  return ['png', 'webp'].includes(extension) || ['image/png', 'image/webp'].includes(file.type)
}

async function decodeMaterialAsset(file: File): Promise<CanvasImageSource & { width?: number; height?: number; naturalWidth?: number; naturalHeight?: number; close?: () => void }> {
  if (typeof createImageBitmap === 'function') return createImageBitmap(file)
  return new Promise((resolve, reject) => {
    const image = new Image()
    const url = URL.createObjectURL(file)
    image.onload = () => {
      URL.revokeObjectURL(url)
      resolve(image)
    }
    image.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('图片无法读取'))
    }
    image.src = url
  })
}

function canvasBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) reject(new Error('浏览器无法生成 WebP，请升级 Chrome 后重试'))
      else resolve(blob)
    }, 'image/webp', 0.92)
  })
}

export async function processMaterialAssetFile(file: File): Promise<ProcessedMaterialAsset> {
  if (!acceptedMaterialAsset(file)) throw new Error('仅支持已抠图的 PNG / WebP')
  if (!file.size) throw new Error('图片文件为空')
  if (file.size > MATERIAL_ASSET_MAX_SOURCE_BYTES) throw new Error('原图不能超过 12MB')

  const image = await decodeMaterialAsset(file)
  try {
    const sourceWidth = image.width || image.naturalWidth || 0
    const sourceHeight = image.height || image.naturalHeight || 0
    if (!sourceWidth || !sourceHeight) throw new Error('无法读取图片尺寸')
    if (sourceWidth * sourceHeight > MATERIAL_ASSET_MAX_SOURCE_PIXELS) throw new Error('原图像素过大，请先缩小后再上传')

    const sourceCanvas = document.createElement('canvas')
    sourceCanvas.width = sourceWidth
    sourceCanvas.height = sourceHeight
    const sourceContext = sourceCanvas.getContext('2d', { willReadFrequently: true })
    if (!sourceContext) throw new Error('浏览器不支持图片处理')
    sourceContext.drawImage(image, 0, 0, sourceWidth, sourceHeight)
    const sourceBounds = materialAssetAlphaBounds(sourceContext.getImageData(0, 0, sourceWidth, sourceHeight).data, sourceWidth, sourceHeight)
    if (!sourceBounds) throw new Error('没有检测到可见主体')
    if (sourceBounds.transparentPixels < Math.max(16, sourceWidth * sourceHeight * 0.001)) {
      throw new Error('未检测到透明背景，请先完成抠图')
    }

    const placement = materialAssetPlacement(sourceBounds)
    const outputCanvas = document.createElement('canvas')
    outputCanvas.width = MATERIAL_ASSET_OUTPUT_SIZE
    outputCanvas.height = MATERIAL_ASSET_OUTPUT_SIZE
    const outputContext = outputCanvas.getContext('2d', { willReadFrequently: true })
    if (!outputContext) throw new Error('浏览器不支持图片处理')
    outputContext.imageSmoothingEnabled = true
    outputContext.imageSmoothingQuality = 'high'
    outputContext.drawImage(image, sourceBounds.left, sourceBounds.top, sourceBounds.width, sourceBounds.height, placement.x, placement.y, placement.width, placement.height)
    const outputBounds = materialAssetAlphaBounds(outputContext.getImageData(0, 0, MATERIAL_ASSET_OUTPUT_SIZE, MATERIAL_ASSET_OUTPUT_SIZE).data, MATERIAL_ASSET_OUTPUT_SIZE, MATERIAL_ASSET_OUTPUT_SIZE)
    const blob = await canvasBlob(outputCanvas)
    if (blob.type !== 'image/webp') throw new Error('当前浏览器不支持 WebP 输出')
    if (blob.size > MATERIAL_ASSET_MAX_OUTPUT_BYTES) throw new Error('处理结果超过 800KB，请压缩原图后重试')
    return { blob, previewUrl: URL.createObjectURL(blob), sourceWidth, sourceHeight, metrics: materialAssetMetrics(outputBounds) }
  } finally {
    image.close?.()
  }
}
