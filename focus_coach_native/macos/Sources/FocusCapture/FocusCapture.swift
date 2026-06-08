// FocusCapture — the simplest native screen-capture loop.
//
// Captures the main display on a timer using ScreenCaptureKit, saves a PNG,
// and (by default) deletes it immediately — proving the "classify then discard,
// nothing is stored" promise at the capture layer. This is the seed of the
// native macOS app; later it grows a menu bar, the Core ML classifier, etc.
//
// Run:  swift run FocusCapture --once            # one capture, keep it, print path
//       swift run FocusCapture                   # loop every 5s, delete each frame
//       swift run FocusCapture --interval 10 --keep --out ~/Desktop/frames
//
// First run triggers the macOS Screen Recording permission prompt (attributed
// to your terminal). Approve it, then run again.

import Foundation
import ScreenCaptureKit
import AppKit

struct Options {
    var interval: Double = 5.0      // seconds between captures
    var once: Bool = false          // single capture then exit
    var keep: Bool = false          // keep the PNG instead of deleting it
    var outDir: URL = FileManager.default.temporaryDirectory
        .appendingPathComponent("focuscapture", isDirectory: true)
}

func parseArgs() -> Options {
    var o = Options()
    var args = Array(CommandLine.arguments.dropFirst())
    var i = 0
    while i < args.count {
        switch args[i] {
        case "--interval":
            if i + 1 < args.count, let v = Double(args[i + 1]) { o.interval = v; i += 1 }
        case "--once":
            o.once = true
        case "--keep":
            o.keep = true
        case "--out":
            if i + 1 < args.count {
                o.outDir = URL(fileURLWithPath: (args[i + 1] as NSString).expandingTildeInPath,
                               isDirectory: true)
                i += 1
            }
        case "--help", "-h":
            print("""
            FocusCapture — native screen capture loop
              --interval <sec>  seconds between captures (default 5)
              --once            capture once and exit
              --keep            keep the PNG (default: delete immediately)
              --out <dir>       where to write frames (default: a temp dir)
            """)
            exit(0)
        default:
            FileHandle.standardError.write("ignoring unknown arg: \(args[i])\n".data(using: .utf8)!)
        }
        i += 1
    }
    return o
}

/// Capture the main display as a CGImage via ScreenCaptureKit.
func captureMainDisplay() async throws -> CGImage {
    // The first call to SCShareableContent triggers the Screen Recording TCC prompt.
    let content = try await SCShareableContent.excludingDesktopWindows(
        false, onScreenWindowsOnly: true)
    guard let display = content.displays.first else {
        throw NSError(domain: "FocusCapture", code: 1,
                      userInfo: [NSLocalizedDescriptionKey: "No display found"])
    }
    let filter = SCContentFilter(display: display, excludingWindows: [])
    let config = SCStreamConfiguration()
    config.width = display.width
    config.height = display.height
    config.showsCursor = false
    return try await SCScreenshotManager.captureImage(
        contentFilter: filter, configuration: config)
}

/// Encode a CGImage to PNG data.
func pngData(_ image: CGImage) -> Data? {
    let rep = NSBitmapImageRep(cgImage: image)
    return rep.representation(using: .png, properties: [:])
}

func timestamp() -> String {
    let f = DateFormatter()
    f.dateFormat = "yyyyMMdd-HHmmss"
    return f.string(from: Date())
}

@main
struct FocusCapture {
    static func main() async {
        let o = parseArgs()
        try? FileManager.default.createDirectory(
            at: o.outDir, withIntermediateDirectories: true)

        FileHandle.standardError.write(
            "[FocusCapture] interval=\(o.interval)s once=\(o.once) keep=\(o.keep) out=\(o.outDir.path)\n"
                .data(using: .utf8)!)

        repeat {
            do {
                let image = try await captureMainDisplay()
                let url = o.outDir.appendingPathComponent("frame-\(timestamp()).png")
                if let data = pngData(image) {
                    try data.write(to: url)
                    if o.keep {
                        print("captured \(image.width)x\(image.height) -> \(url.path)")
                    } else {
                        try? FileManager.default.removeItem(at: url)
                        print("captured \(image.width)x\(image.height) (discarded, not stored)")
                    }
                } else {
                    FileHandle.standardError.write("[FocusCapture] PNG encode failed\n".data(using: .utf8)!)
                }
            } catch {
                FileHandle.standardError.write(
                    "[FocusCapture] capture failed: \(error.localizedDescription)\n"
                        .data(using: .utf8)!)
                FileHandle.standardError.write(
                    "  If this is a permission error, grant Screen Recording to your terminal in\n  System Settings > Privacy & Security > Screen Recording, then re-run.\n"
                        .data(using: .utf8)!)
                if o.once { exit(1) }
            }

            if o.once { break }
            try? await Task.sleep(nanoseconds: UInt64(o.interval * 1_000_000_000))
        } while true
    }
}
