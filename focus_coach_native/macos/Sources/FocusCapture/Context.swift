// Context — cheap OS signals for the heuristic classifier.
//
// Two signals, both native and both already permitted:
//   * frontmost app name  — NSWorkspace, no extra permission.
//   * frontmost window title — CGWindowList. `kCGWindowName` is only populated
//     when the process holds the Screen Recording permission, which this app
//     already requires to capture. So we get titles for free, with NO separate
//     Accessibility (AXIsProcessTrusted) prompt.
//
// Privacy: we read only the window *title* (e.g. "Inbox — Mail"), never window
// contents, and the title never leaves the machine — it only steers the local
// heuristic and is summarised, not logged verbatim, as activity.

import Foundation
import AppKit
import CoreGraphics

enum OSContext {
    /// Localized name of the frontmost application (e.g. "Safari"). "" if none.
    static func frontmostApp() -> (name: String, pid: pid_t?) {
        guard let app = NSWorkspace.shared.frontmostApplication else { return ("", nil) }
        return (app.localizedName ?? "", app.processIdentifier)
    }

    /// Best-effort title of the frontmost window of `pid`. Uses the on-screen
    /// window list, picking the front-most (lowest layer / first in z-order)
    /// normal window owned by that process. Returns "" if unavailable.
    static func frontmostWindowTitle(pid: pid_t?) -> String {
        guard let pid = pid else { return "" }
        let options: CGWindowListOption = [.optionOnScreenOnly, .excludeDesktopElements]
        guard let infoList = CGWindowListCopyWindowInfo(options, kCGNullWindowID)
                as? [[String: Any]] else { return "" }

        // The list is ordered front-to-back. Take the first window that belongs
        // to the frontmost app, sits on the normal layer (0), and has a title.
        for win in infoList {
            guard let ownerPID = win[kCGWindowOwnerPID as String] as? pid_t,
                  ownerPID == pid else { continue }
            let layer = (win[kCGWindowLayer as String] as? Int) ?? 0
            if layer != 0 { continue }                 // skip menubar/overlays
            if let name = win[kCGWindowName as String] as? String, !name.isEmpty {
                return name
            }
        }
        return ""
    }

    /// Gather the full context in one call.
    static func gather() -> Context {
        let (name, pid) = frontmostApp()
        let title = frontmostWindowTitle(pid: pid)
        return Context(app: name, title: title, faceCount: 0)
    }
}
