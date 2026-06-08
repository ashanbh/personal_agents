// Classifier — Tier-3 heuristic, native Swift port of app/backends.py.
//
// No model, no download, cross-platform-friendly logic: decide "is the user
// working?" from the frontmost app name, the window title, and (optionally) a
// face count. This is the guaranteed fallback tier — it always works, on day
// one, with nothing installed. The vision tiers (Apple Foundation Models on
// macOS, bundled ONNX VLM on Windows) plug in behind the same `Classifier`
// protocol later and consume the captured frame; the heuristic ignores it.
//
// Kept deliberately faithful to the Python HeuristicBackend so the two stay in
// sync (the Python version has unit tests; this mirrors its cases).

import Foundation

/// A classification result. Mirrors the readout dict in backends.py.
struct Readout {
    enum Category: String { case working, not_working, unknown }

    var category: Category
    var focused: Bool
    var activity: String   // 2–4 word label
    var summary: String    // one short sentence, NO personal screen content

    static func empty(_ category: Category = .unknown,
                      activity: String = "unknown",
                      summary: String = "",
                      focused: Bool = false) -> Readout {
        Readout(category: category, focused: focused,
                activity: activity, summary: summary)
    }
}

/// OS context handed to a classifier. Mirrors `ctx` in the Python service.
struct Context {
    var app: String = ""        // frontmost application name
    var title: String = ""      // frontmost window title (best effort)
    var faceCount: Int = 0      // optional face pre-pass (0 when none/unavailable)
}

/// The pluggable backend interface. Vision tiers adopt this later.
protocol Classifier {
    var name: String { get }
    /// `frame` may be nil for backends that classify from context alone.
    func classify(frame: CGImage?, context: Context) -> Readout
}

/// Tier 3 — heuristic. Frontmost app + window title + face count. No LLM.
struct HeuristicClassifier: Classifier {
    let name = "heuristic"

    // App-name substrings (lowercased) -> strong work signal.
    private static let workApps: [String] = [
        "code", "xcode", "terminal", "iterm", "intellij", "pycharm", "webstorm",
        "cursor", "visual studio", "sublime", "vim", "emacs", "nova", "zed",
        "slack", "mail", "spark", "outlook", "notion", "obsidian", "bear",
        "word", "excel", "powerpoint", "pages", "numbers", "keynote", "docs",
        "sheets", "figma", "sketch", "balsamiq", "zoom", "meet", "teams", "webex",
        "linear", "jira", "asana", "github", "sourcetree", "postman", "tableplus",
        "pgadmin", "datagrip", "preview", "acrobat", "calendar", "fantastical",
    ]
    // App-name substrings -> strong distraction signal.
    private static let distractApps: [String] = [
        "netflix", "hulu", "disney", "prime video", "sling", "twitch", "tv",
        "spotify", "music", "podcasts", "steam", "game", "discord", "whatsapp",
        "messages", "tiktok", "instagram",
    ]
    // Browsers are ambiguous — decide from the window title.
    private static let browsers: [String] = [
        "safari", "chrome", "firefox", "edge", "arc", "brave", "opera",
    ]
    private static let titleWork: [String] = [
        "github", "gitlab", "stack overflow", "stackoverflow", "jira", "linear",
        "docs.", "developer.", "notion", "confluence", "google docs", "sheets",
        "localhost", "pull request", "documentation", "api reference", "aws",
        "console", "dashboard",
    ]
    private static let titleDistract: [String] = [
        "youtube", "reddit", "twitter", "x.com", "facebook", "instagram", "tiktok",
        "netflix", "twitch", "espn", "amazon", "ebay", "news", "9gag", "imgur",
    ]

    private func matches(_ text: String, _ needles: [String]) -> Bool {
        let t = text.lowercased()
        return needles.contains { t.contains($0) }
    }

    func classify(frame: CGImage?, context ctx: Context) -> Readout {
        let app = ctx.app.trimmingCharacters(in: .whitespacesAndNewlines)
        let title = ctx.title.trimmingCharacters(in: .whitespacesAndNewlines)
        let appL = app.lowercased()

        // Multiple faces on screen -> almost certainly a video meeting.
        if ctx.faceCount >= 2 {
            return .empty(.working, activity: "video meeting",
                          summary: "\(app.isEmpty ? "app" : app) showing multiple participants",
                          focused: true)
        }

        if matches(appL, Self.workApps) {
            return .empty(.working, activity: "focused work",
                          summary: "using \(app)", focused: true)
        }

        if matches(appL, Self.distractApps) {
            return .empty(.not_working, activity: "leisure",
                          summary: "using \(app)", focused: false)
        }

        if Self.browsers.contains(where: { appL.contains($0) }) {
            if matches(title, Self.titleDistract) {
                return .empty(.not_working, activity: "browsing (leisure)",
                              summary: "leisure site in browser", focused: false)
            }
            if matches(title, Self.titleWork) {
                return .empty(.working, activity: "browsing (work)",
                              summary: "work site in browser", focused: true)
            }
            return .empty(.unknown, activity: "browsing",
                          summary: "\(app): unclassified page", focused: false)
        }

        // No signal we trust.
        let label = app.isEmpty ? "no foreground app detected" : "using \(app)"
        return .empty(.unknown, activity: "unclassified", summary: label, focused: false)
    }
}
