import AppKit
import CoreGraphics
import Foundation

/// Polls frontmost-app metadata every `tickIntervalS`, classifies, persists,
/// and feeds the session engine. M1 is metadata-only: no screen frames, no camera.
public final class Poller {
    public let tickIntervalS: Int
    private let store: EventStore
    private let engine: SessionEngine
    private var classifier: Classifier
    private var timer: Timer?
    public private(set) var paused = false
    public private(set) var lastCategory: Category = .unknown
    public var onTick: ((Tick, Bool) -> Void)? // (tick, sessionOpen)

    public init(store: EventStore, engine: SessionEngine, classifier: Classifier,
                tickIntervalS: Int = 5) {
        self.store = store
        self.engine = engine
        self.classifier = classifier
        self.tickIntervalS = tickIntervalS
    }

    public func setClassifier(_ c: Classifier) { classifier = c }

    public func start() {
        timer?.invalidate()
        let t = Timer(timeInterval: TimeInterval(tickIntervalS), repeats: true) { [weak self] _ in
            self?.tick()
        }
        RunLoop.main.add(t, forMode: .common)
        timer = t
        tick()
    }

    public func setPaused(_ p: Bool) {
        paused = p
        if p { engine.close(reason: "quit") }
    }

    public func stop() {
        timer?.invalidate()
        timer = nil
        engine.close(reason: "quit")
    }

    private func tick() {
        guard !paused else { return }

        let idle = Poller.idleSeconds()
        guard let front = NSWorkspace.shared.frontmostApplication else {
            engine.tick(category: .unknown, idleSeconds: idle)
            return
        }
        let bundleId = front.bundleIdentifier
        let appName = front.localizedName

        var domain: String? = nil
        if let bid = bundleId, Classifier.browserBundleIds.contains(bid), idle < 60 {
            domain = BrowserURL.domain(forBundleId: bid)
        }

        let tick = classifier.classify(bundleId: bundleId, appName: appName, domain: domain)
        lastCategory = tick.category

        // Don't record history while idle — there is nothing to attribute.
        if idle < 120 {
            store.insert(tick)
        }
        engine.tick(category: tick.category, idleSeconds: idle)
        onTick?(tick, engine.isOpen)
    }

    /// Seconds since last user input (min across common input event types).
    public static func idleSeconds() -> Double {
        let types: [CGEventType] = [.keyDown, .mouseMoved, .leftMouseDown,
                                    .rightMouseDown, .scrollWheel]
        return types.map {
            CGEventSource.secondsSinceLastEventType(.combinedSessionState, eventType: $0)
        }.min() ?? 0
    }
}
