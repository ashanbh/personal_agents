// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "FocusCapture",
    platforms: [
        // SCScreenshotManager (one-shot capture) requires macOS 14.
        .macOS(.v14)
    ],
    targets: [
        .executableTarget(
            name: "FocusCapture",
            path: "Sources/FocusCapture"
        )
    ]
)
