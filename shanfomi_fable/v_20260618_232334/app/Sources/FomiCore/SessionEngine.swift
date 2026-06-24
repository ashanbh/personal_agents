import Foundation

/// Auto-session state machine (DESIGN.md §3.3). Pure logic, no AppKit — unit-testable.
///
/// Open:  `openAfterWorkTicks` consecutive work ticks.
/// Close: idle >= `closeAfterIdleS`, or `closeAfterNonworkTicks` consecutive
///        not-work ticks while a session is open.
public final class SessionEngine {
    public struct Config {
        public var tickIntervalS: Int
        public var openAfterWorkTicks: Int
        public var closeAfterIdleS: Int
        public var closeAfterNonworkTicks: Int
        public init(tickIntervalS: Int = 5, openAfterWorkTicks: Int = 3,
                    closeAfterIdleS: Int = 600, closeAfterNonworkTicks: Int = 60) {
            self.tickIntervalS = tickIntervalS
            self.openAfterWorkTicks = openAfterWorkTicks
            self.closeAfterIdleS = closeAfterIdleS
            self.closeAfterNonworkTicks = closeAfterNonworkTicks
        }
    }

    public private(set) var sessionStart: Date?
    public var isOpen: Bool { sessionStart != nil }

    private let config: Config
    private var consecutiveWork = 0
    private var consecutiveNonwork = 0
    private var workTicksInSession = 0
    private var nonworkTicksInSession = 0

    /// (start, end, workS, nonworkS, reason)
    public var onClose: ((Date, Date, Int, Int, String) -> Void)?
    public var onOpen: ((Date) -> Void)?

    public init(config: Config = Config()) {
        self.config = config
    }

    public func tick(category: Category, idleSeconds: Double, now: Date = Date()) {
        if idleSeconds >= Double(config.closeAfterIdleS) {
            // Idle long enough: close any open session, reset counters.
            close(at: now.addingTimeInterval(-idleSeconds), reason: "idle")
            consecutiveWork = 0
            consecutiveNonwork = 0
            return
        }

        let isWork = (category == .work || category == .privateWork)
        let isNonwork = (category == .nonwork || category == .privateNonwork)

        if isWork {
            consecutiveWork += 1
            consecutiveNonwork = 0
        } else if isNonwork {
            consecutiveNonwork += 1
            consecutiveWork = 0
        }
        // unknown: neutral — breaks the work streak but doesn't count toward closing.
        else {
            consecutiveWork = 0
        }

        if isOpen {
            if isWork { workTicksInSession += 1 }
            if isNonwork { nonworkTicksInSession += 1 }
            if consecutiveNonwork >= config.closeAfterNonworkTicks {
                close(at: now, reason: "nonwork")
            }
        } else if consecutiveWork >= config.openAfterWorkTicks {
            sessionStart = now.addingTimeInterval(-Double(consecutiveWork * config.tickIntervalS))
            workTicksInSession = consecutiveWork
            nonworkTicksInSession = 0
            onOpen?(sessionStart!)
        }
    }

    public func close(at end: Date = Date(), reason: String) {
        guard let start = sessionStart else { return }
        sessionStart = nil
        let workS = workTicksInSession * config.tickIntervalS
        let nonworkS = nonworkTicksInSession * config.tickIntervalS
        workTicksInSession = 0
        nonworkTicksInSession = 0
        onClose?(start, max(start, end), workS, nonworkS, reason)
    }
}
