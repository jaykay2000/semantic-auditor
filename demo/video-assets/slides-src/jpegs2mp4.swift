// Encode a numbered JPEG sequence to an H.264 MP4 with AVFoundation (no ffmpeg needed).
//   swift jpegs2mp4.swift <frames-dir> <fps> <out.mp4>
// Frames are read in name order; every frame must be the same size.
import AVFoundation
import CoreGraphics
import ImageIO
import Foundation

let args = CommandLine.arguments
guard args.count == 4, let fps = Int32(args[2]) else { print("usage: jpegs2mp4 <dir> <fps> <out.mp4>"); exit(2) }
let dir = URL(fileURLWithPath: args[1]), out = URL(fileURLWithPath: args[3])
let files = try FileManager.default.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil)
  .filter { $0.pathExtension.lowercased() == "jpg" }.sorted { $0.lastPathComponent < $1.lastPathComponent }
guard let first = files.first, let src0 = CGImageSourceCreateWithURL(first as CFURL, nil),
      let img0 = CGImageSourceCreateImageAtIndex(src0, 0, nil) else { print("no frames"); exit(1) }
let w = img0.width, h = img0.height
try? FileManager.default.removeItem(at: out)
let writer = try AVAssetWriter(outputURL: out, fileType: .mp4)
let input = AVAssetWriterInput(mediaType: .video, outputSettings: [
  AVVideoCodecKey: AVVideoCodecType.h264, AVVideoWidthKey: w, AVVideoHeightKey: h,
  AVVideoCompressionPropertiesKey: [AVVideoAverageBitRateKey: 16_000_000, AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel,
                                    AVVideoMaxKeyFrameIntervalKey: Int(fps) * 2]])
input.expectsMediaDataInRealTime = false
let adaptor = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: input, sourcePixelBufferAttributes: [
  kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32ARGB, kCVPixelBufferWidthKey as String: w, kCVPixelBufferHeightKey as String: h])
writer.add(input); writer.startWriting(); writer.startSession(atSourceTime: .zero)
for (i, f) in files.enumerated() {
  guard let s = CGImageSourceCreateWithURL(f as CFURL, nil), let img = CGImageSourceCreateImageAtIndex(s, 0, nil) else { print("bad frame \(f)"); exit(1) }
  while !input.isReadyForMoreMediaData { usleep(2000) }
  var pb: CVPixelBuffer?
  CVPixelBufferPoolCreatePixelBuffer(nil, adaptor.pixelBufferPool!, &pb)
  CVPixelBufferLockBaseAddress(pb!, [])
  let ctx = CGContext(data: CVPixelBufferGetBaseAddress(pb!), width: w, height: h, bitsPerComponent: 8,
                      bytesPerRow: CVPixelBufferGetBytesPerRow(pb!), space: CGColorSpace(name: CGColorSpace.sRGB)!,
                      bitmapInfo: CGImageAlphaInfo.noneSkipFirst.rawValue)!
  ctx.draw(img, in: CGRect(x: 0, y: 0, width: w, height: h))
  CVPixelBufferUnlockBaseAddress(pb!, [])
  adaptor.append(pb!, withPresentationTime: CMTime(value: CMTimeValue(i), timescale: fps))
}
input.markAsFinished()
let sem = DispatchSemaphore(value: 0)
writer.finishWriting { sem.signal() }
sem.wait()
if writer.status != .completed { print("failed: \(String(describing: writer.error))"); exit(1) }
print("wrote \(out.path) (\(files.count) frames, \(w)x\(h))")
