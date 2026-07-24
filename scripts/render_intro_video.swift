import AVFoundation
import CoreGraphics
import Foundation
import ImageIO

let arguments = CommandLine.arguments
guard arguments.count == 3 else {
    fputs("Usage: render_intro_video <captures-dir> <output.mp4>\n", stderr)
    exit(2)
}

let capturesURL = URL(fileURLWithPath: arguments[1], isDirectory: true)
let outputURL = URL(fileURLWithPath: arguments[2])
let captureURLs = try FileManager.default.contentsOfDirectory(
    at: capturesURL,
    includingPropertiesForKeys: nil
).filter { $0.pathExtension.lowercased() == "png" }.sorted { $0.lastPathComponent < $1.lastPathComponent }

guard let firstURL = captureURLs.first,
      let firstSource = CGImageSourceCreateWithURL(firstURL as CFURL, nil),
      let firstImage = CGImageSourceCreateImageAtIndex(firstSource, 0, nil) else {
    fputs("No readable PNG captures found.\n", stderr)
    exit(2)
}

let width = firstImage.width
let height = firstImage.height
let fps: Int32 = 30
let videoSettings: [String: Any] = [
    AVVideoCodecKey: AVVideoCodecType.h264,
    AVVideoWidthKey: width,
    AVVideoHeightKey: height,
    AVVideoCompressionPropertiesKey: [
        AVVideoAverageBitRateKey: 3_000_000,
        AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel
    ]
]

try? FileManager.default.removeItem(at: outputURL)
let writer = try AVAssetWriter(outputURL: outputURL, fileType: .mp4)
let input = AVAssetWriterInput(mediaType: .video, outputSettings: videoSettings)
input.expectsMediaDataInRealTime = false
let adaptor = AVAssetWriterInputPixelBufferAdaptor(
    assetWriterInput: input,
    sourcePixelBufferAttributes: [
        kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
        kCVPixelBufferWidthKey as String: width,
        kCVPixelBufferHeightKey as String: height,
        kCVPixelBufferCGImageCompatibilityKey as String: true,
        kCVPixelBufferCGBitmapContextCompatibilityKey as String: true
    ]
)
guard writer.canAdd(input) else { throw NSError(domain: "video", code: 1) }
writer.add(input)
guard writer.startWriting() else { throw writer.error ?? NSError(domain: "video", code: 2) }
writer.startSession(atSourceTime: .zero)

func makeBuffer(image: CGImage) -> CVPixelBuffer? {
    var buffer: CVPixelBuffer?
    guard CVPixelBufferPoolCreatePixelBuffer(nil, adaptor.pixelBufferPool!, &buffer) == kCVReturnSuccess,
          let output = buffer else { return nil }
    CVPixelBufferLockBaseAddress(output, [])
    defer { CVPixelBufferUnlockBaseAddress(output, []) }
    guard let context = CGContext(
        data: CVPixelBufferGetBaseAddress(output),
        width: width,
        height: height,
        bitsPerComponent: 8,
        bytesPerRow: CVPixelBufferGetBytesPerRow(output),
        space: CGColorSpaceCreateDeviceRGB(),
        bitmapInfo: CGImageAlphaInfo.premultipliedFirst.rawValue | CGBitmapInfo.byteOrder32Little.rawValue
    ) else { return nil }
    context.setFillColor(CGColor(gray: 1, alpha: 1))
    context.fill(CGRect(x: 0, y: 0, width: width, height: height))
    context.draw(image, in: CGRect(x: 0, y: 0, width: width, height: height))
    return output
}

var frame: Int64 = 0
for (index, url) in captureURLs.enumerated() {
    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil),
          let buffer = makeBuffer(image: image) else { continue }
    let seconds = (index == 0 || index == captureURLs.count - 1) ? 2.6 : 1.8
    let count = Int((seconds * Double(fps)).rounded())
    for _ in 0..<count {
        while !input.isReadyForMoreMediaData { Thread.sleep(forTimeInterval: 0.01) }
        let time = CMTime(value: frame, timescale: fps)
        guard adaptor.append(buffer, withPresentationTime: time) else {
            throw writer.error ?? NSError(domain: "video", code: 3)
        }
        frame += 1
    }
}

input.markAsFinished()
let completion = DispatchSemaphore(value: 0)
writer.finishWriting { completion.signal() }
completion.wait()
guard writer.status == .completed else { throw writer.error ?? NSError(domain: "video", code: 4) }
print(outputURL.path)
