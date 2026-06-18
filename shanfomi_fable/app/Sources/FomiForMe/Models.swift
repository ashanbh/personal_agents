import Foundation

/// Categories persisted to the event store.
/// DESIGN.md §2.3: sensitive matches collapse to a `private-*` category and
/// their identifiers (bundle id, app name, domain) are NEVER persisted.
public enum Category: String {
    case work = "work"
    case nonwork = "nonwork"
    case privateWork = "private-work"
    case privateNonwork = "private-nonwork"
    case unknown = "unknown"
}

/// One classified observation tick.
public struct Tick {
    public let date: Date
    public let bundleId: String?
    public let appName: String?
    public let domain: String?
    public let category: Category
    public let confidence: Double
    public let tier: Int // 0 = rules; 1 = vision (M3); 2 = LLM (M2)

    public init(date: Date = Date(), bundleId: String?, appName: String?,
                domain: String?, category: Category, confidence: Double, tier: Int) {
        self.date = date
        self.bundleId = bundleId
        self.appName = appName
        self.domain = domain
        self.category = category
        self.confidence = confidence
        self.tier = tier
    }

    /// Privacy invariant: a tick in a private bucket carries no identifiers.
    public func sanitized() -> Tick {
        guard category == .privateWork || category == .privateNonwork else { return self }
        return Tick(date: date, bundleId: nil, appName: nil, domain: nil,
                    category: category, confidence: confidence, tier: tier)
    }
}
