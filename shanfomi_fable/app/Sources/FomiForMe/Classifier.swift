import Foundation

/// Tier-0 rule classifier. Order of precedence (DESIGN.md §3.2):
///   1. Explicit persona WORK match (lets an accountant mark bank portals work
///      even if globally "personal finance" is sensitive).
///   2. Sensitive collapse -> private-nonwork.
///   3. Persona NONWORK match.
///   4. Browser with no readable domain, or anything unmatched -> unknown
///      (T2 LLM territory in M2; in M1 unknown is neutral).
public struct Classifier {
    public let pack: RulePack
    public let sensitive: SensitiveMap

    public init(pack: RulePack, sensitive: SensitiveMap) {
        self.pack = pack
        self.sensitive = sensitive
    }

    public static let browserBundleIds: Set<String> = [
        "com.apple.Safari", "com.google.Chrome", "org.mozilla.firefox",
        "com.microsoft.edgemac", "com.brave.Browser", "company.thebrowser.Browser",
    ]

    public func classify(bundleId: String?, appName: String?, domain: String?) -> Tick {
        let bid = bundleId ?? ""
        let app = (appName ?? "").lowercased()
        let dom = (domain ?? "").lowercased()

        func bundleMatch(_ prefixes: [String]) -> Bool {
            prefixes.contains { !$0.isEmpty && bid.hasPrefix($0) }
        }
        func domainMatch(_ suffixes: [String]) -> Bool {
            guard !dom.isEmpty else { return false }
            return suffixes.contains { !$0.isEmpty && (dom == $0 || dom.hasSuffix("." + $0)) }
        }
        func appMatch(_ subs: [String]) -> Bool {
            guard !app.isEmpty else { return false }
            return subs.contains { !$0.isEmpty && app.contains($0.lowercased()) }
        }
        func make(_ c: Category, _ conf: Double) -> Tick {
            Tick(bundleId: bundleId, appName: appName, domain: domain,
                 category: c, confidence: conf, tier: 0).sanitized()
        }

        // 1. Meetings and explicit persona work.
        if bundleMatch(pack.meetingBundlePrefixes) { return make(.work, 0.95) }
        if domainMatch(pack.workDomainSuffixes) { return make(.work, 0.9) }
        let isBrowser = Classifier.browserBundleIds.contains(bid)
        if !isBrowser && (bundleMatch(pack.workBundlePrefixes) || appMatch(pack.workAppSubstrings)) {
            return make(.work, 0.9)
        }

        // 2. Sensitive collapse (identifiers stripped by sanitized()).
        if domainMatch(sensitive.privateDomainSuffixes)
            || bundleMatch(sensitive.privateBundlePrefixes)
            || appMatch(sensitive.privateAppSubstrings) {
            return make(.privateNonwork, 0.9)
        }

        // 3. Persona nonwork.
        if domainMatch(pack.nonworkDomainSuffixes) { return make(.nonwork, 0.9) }
        if !isBrowser && (bundleMatch(pack.nonworkBundlePrefixes) || appMatch(pack.nonworkAppSubstrings)) {
            return make(.nonwork, 0.9)
        }

        // 4. Unknown (browser with unreadable/unlisted domain, unlisted app).
        return make(.unknown, 0.4)
    }
}
