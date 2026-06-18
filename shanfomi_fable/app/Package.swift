// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "FomiForMe",
    platforms: [.macOS(.v13)],
    targets: [
        // All logic + rule-pack resources live in a library so tests can import
        // it cleanly and Bundle.module resolves the Rules/ resources.
        .target(
            name: "FomiCore",
            path: "Sources/FomiCore",
            resources: [.copy("Rules")]
        ),
        // Thin executable: just launches the AppKit app from FomiCore.
        .executableTarget(
            name: "FomiForMe",
            dependencies: ["FomiCore"],
            path: "Sources/FomiForMe"
        ),
        .testTarget(
            name: "FomiCoreTests",
            dependencies: ["FomiCore"],
            path: "Tests/FomiCoreTests"
        ),
    ]
)
