import Foundation

/// Reads the frontmost browser tab's URL host via AppleScript (metadata only —
/// no page content). First call per browser triggers the macOS Automation
/// permission prompt; on denial we degrade to `nil` → category `unknown`.
public enum BrowserURL {
    public static func domain(forBundleId bundleId: String) -> String? {
        guard let script = script(for: bundleId) else { return nil }
        var error: NSDictionary?
        guard let result = NSAppleScript(source: script)?.executeAndReturnError(&error),
              error == nil,
              let urlString = result.stringValue,
              let host = URL(string: urlString)?.host else { return nil }
        return host.hasPrefix("www.") ? String(host.dropFirst(4)) : host
    }

    private static func script(for bundleId: String) -> String? {
        switch bundleId {
        case "com.apple.Safari":
            return #"tell application "Safari" to return URL of front document"#
        case "com.google.Chrome", "com.brave.Browser", "com.microsoft.edgemac",
             "company.thebrowser.Browser":
            return "tell application id \"\(bundleId)\" to return URL of active tab of front window"
        default:
            return nil
        }
    }
}
