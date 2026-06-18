import XCTest
@testable import FomiCore

final class SessionEngineTests: XCTestCase {
    func testOpensAfterConsecutiveWorkTicks() {
        let e = SessionEngine(config: .init(tickIntervalS: 5, openAfterWorkTicks: 3,
                                            closeAfterIdleS: 600, closeAfterNonworkTicks: 60))
        var opened = false
        e.onOpen = { _ in opened = true }
        e.tick(category: .work, idleSeconds: 0)
        e.tick(category: .work, idleSeconds: 0)
        XCTAssertFalse(e.isOpen)
        e.tick(category: .work, idleSeconds: 0)
        XCTAssertTrue(e.isOpen)
        XCTAssertTrue(opened)
    }

    func testNonworkBreaksOpeningStreak() {
        let e = SessionEngine(config: .init(tickIntervalS: 5, openAfterWorkTicks: 3,
                                            closeAfterIdleS: 600, closeAfterNonworkTicks: 60))
        e.tick(category: .work, idleSeconds: 0)
        e.tick(category: .work, idleSeconds: 0)
        e.tick(category: .nonwork, idleSeconds: 0)
        e.tick(category: .work, idleSeconds: 0)
        XCTAssertFalse(e.isOpen)
    }

    func testClosesOnIdle() {
        let e = SessionEngine(config: .init(tickIntervalS: 5, openAfterWorkTicks: 1,
                                            closeAfterIdleS: 600, closeAfterNonworkTicks: 60))
        var reason: String?
        e.onClose = { _, _, _, _, r in reason = r }
        e.tick(category: .work, idleSeconds: 0)
        XCTAssertTrue(e.isOpen)
        e.tick(category: .work, idleSeconds: 601)
        XCTAssertFalse(e.isOpen)
        XCTAssertEqual(reason, "idle")
    }

    func testClosesOnSustainedNonwork() {
        let e = SessionEngine(config: .init(tickIntervalS: 5, openAfterWorkTicks: 1,
                                            closeAfterIdleS: 600, closeAfterNonworkTicks: 3))
        var closed: (Int, Int, String)?
        e.onClose = { _, _, w, n, r in closed = (w, n, r) }
        e.tick(category: .work, idleSeconds: 0)
        e.tick(category: .work, idleSeconds: 0)
        e.tick(category: .nonwork, idleSeconds: 0)
        e.tick(category: .nonwork, idleSeconds: 0)
        e.tick(category: .nonwork, idleSeconds: 0)
        XCTAssertFalse(e.isOpen)
        XCTAssertEqual(closed?.2, "nonwork")
        XCTAssertEqual(closed?.0, 10) // 2 work ticks * 5s
    }

    func testUnknownIsNeutral() {
        let e = SessionEngine(config: .init(tickIntervalS: 5, openAfterWorkTicks: 1,
                                            closeAfterIdleS: 600, closeAfterNonworkTicks: 3))
        e.tick(category: .work, idleSeconds: 0)
        XCTAssertTrue(e.isOpen)
        for _ in 0..<10 { e.tick(category: .unknown, idleSeconds: 0) }
        XCTAssertTrue(e.isOpen) // unknown never closes a session
    }
}
