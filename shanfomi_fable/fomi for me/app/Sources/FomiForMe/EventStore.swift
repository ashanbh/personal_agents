import Foundation
import SQLite3

private let SQLITE_TRANSIENT = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

/// SQLite event store. Persists ONLY derived events (DESIGN.md §3.4).
/// The API accepts `Tick` (already sanitized) — raw frames can never reach here
/// because no API takes pixel data.
public final class EventStore {
    private var db: OpaquePointer?
    public let path: String

    public init(path: String) throws {
        self.path = (path as NSString).expandingTildeInPath
        let dir = (self.path as NSString).deletingLastPathComponent
        try FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
        guard sqlite3_open(self.path, &db) == SQLITE_OK else {
            throw NSError(domain: "FomiForMe", code: 2,
                          userInfo: [NSLocalizedDescriptionKey: "Cannot open DB at \(self.path)"])
        }
        try exec("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,                -- unix epoch seconds
            bundle_id TEXT,                  -- NULL for private-* categories
            app_name TEXT,                   -- NULL for private-* categories
            domain TEXT,                     -- NULL for private-* categories
            category TEXT NOT NULL,
            confidence REAL NOT NULL,
            tier INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_ts REAL NOT NULL,
            end_ts REAL NOT NULL,
            work_s INTEGER NOT NULL,
            nonwork_s INTEGER NOT NULL,
            close_reason TEXT NOT NULL       -- 'idle' | 'nonwork' | 'quit'
        );
        -- Forward-compat (M2/M5): justifications, goals (DESIGN.md §3.3/3.6).
        CREATE TABLE IF NOT EXISTS justifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            claim TEXT NOT NULL,
            context_summary TEXT,
            accepted INTEGER NOT NULL,
            goal_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT NOT NULL,               -- YYYY-MM-DD local
            text TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'user'
        );
        """)
    }

    deinit { sqlite3_close(db) }

    private func exec(_ sql: String) throws {
        var err: UnsafeMutablePointer<CChar>?
        guard sqlite3_exec(db, sql, nil, nil, &err) == SQLITE_OK else {
            let msg = err.map { String(cString: $0) } ?? "unknown sqlite error"
            sqlite3_free(err)
            throw NSError(domain: "FomiForMe", code: 3, userInfo: [NSLocalizedDescriptionKey: msg])
        }
    }

    public func insert(_ tick: Tick) {
        let t = tick.sanitized() // belt-and-suspenders: enforce invariant at the write boundary
        let sql = "INSERT INTO events (ts, bundle_id, app_name, domain, category, confidence, tier) VALUES (?,?,?,?,?,?,?)"
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return }
        defer { sqlite3_finalize(stmt) }
        sqlite3_bind_double(stmt, 1, t.date.timeIntervalSince1970)
        bindText(stmt, 2, t.bundleId)
        bindText(stmt, 3, t.appName)
        bindText(stmt, 4, t.domain)
        bindText(stmt, 5, t.category.rawValue)
        sqlite3_bind_double(stmt, 6, t.confidence)
        sqlite3_bind_int(stmt, 7, Int32(t.tier))
        sqlite3_step(stmt)
    }

    public func insertSession(start: Date, end: Date, workS: Int, nonworkS: Int, reason: String) {
        let sql = "INSERT INTO sessions (start_ts, end_ts, work_s, nonwork_s, close_reason) VALUES (?,?,?,?,?)"
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return }
        defer { sqlite3_finalize(stmt) }
        sqlite3_bind_double(stmt, 1, start.timeIntervalSince1970)
        sqlite3_bind_double(stmt, 2, end.timeIntervalSince1970)
        sqlite3_bind_int(stmt, 3, Int32(workS))
        sqlite3_bind_int(stmt, 4, Int32(nonworkS))
        bindText(stmt, 5, reason)
        sqlite3_step(stmt)
    }

    /// (workSeconds, nonworkSeconds) since local midnight, derived from tick counts.
    public func todayTotals(tickInterval: Int) -> (work: Int, nonwork: Int) {
        let midnight = Calendar.current.startOfDay(for: Date()).timeIntervalSince1970
        let sql = "SELECT category, COUNT(*) FROM events WHERE ts >= ? GROUP BY category"
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return (0, 0) }
        defer { sqlite3_finalize(stmt) }
        sqlite3_bind_double(stmt, 1, midnight)
        var work = 0, nonwork = 0
        while sqlite3_step(stmt) == SQLITE_ROW {
            let cat = String(cString: sqlite3_column_text(stmt, 0))
            let n = Int(sqlite3_column_int(stmt, 1)) * tickInterval
            switch cat {
            case Category.work.rawValue, Category.privateWork.rawValue: work += n
            case Category.nonwork.rawValue, Category.privateNonwork.rawValue: nonwork += n
            default: break
            }
        }
        return (work, nonwork)
    }

    private func bindText(_ stmt: OpaquePointer?, _ idx: Int32, _ value: String?) {
        if let v = value {
            sqlite3_bind_text(stmt, idx, v, -1, SQLITE_TRANSIENT)
        } else {
            sqlite3_bind_null(stmt, idx)
        }
    }
}
