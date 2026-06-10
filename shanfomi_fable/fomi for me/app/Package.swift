// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "FomiForMe",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "FomiForMe",
            path: "Sources/FomiForMe",
            resources: [.copy("Rules")]
        ),
        .testTarget(
            name: "FomiForMeTests",
            dependencies: ["FomiForMe"],
            path: "Tests/FomiForMeTests"
        ),
    ]
)
