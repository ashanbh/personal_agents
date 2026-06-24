import AppKit
import Foundation

public final class AppDelegate: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem!
    private var store: EventStore!
    private var engine: SessionEngine!
    private var poller: Poller!

    private let stateLine = NSMenuItem(title: "Starting…", action: nil, keyEquivalent: "")
    private let totalsLine = NSMenuItem(title: "Today: —", action: nil, keyEquivalent: "")
    private let pauseItem = NSMenuItem(title: "Pause monitoring",
                                       action: #selector(togglePause), keyEquivalent: "p")
    private var personaItems: [NSMenuItem] = []

    public override init() { super.init() }

    private var persona: String {
        get { UserDefaults.standard.string(forKey: "persona") ?? "engineer" }
        set { UserDefaults.standard.set(newValue, forKey: "persona") }
    }

    public func applicationDidFinishLaunching(_ notification: Notification) {
        do {
            let dbPath = ProcessInfo.processInfo.environment["FOMI4ME_DB"]
                ?? "~/Library/Application Support/FomiForMe/fomi4me.sqlite"
            store = try EventStore(path: dbPath)
            engine = SessionEngine()
            let classifier = try makeClassifier(persona: persona)
            poller = Poller(store: store, engine: engine, classifier: classifier)
        } catch {
            NSLog("FomiForMe fatal: \(error.localizedDescription)")
            NSApp.terminate(nil)
            return
        }

        engine.onClose = { [weak self] start, end, workS, nonworkS, reason in
            self?.store.insertSession(start: start, end: end, workS: workS,
                                      nonworkS: nonworkS, reason: reason)
        }
        poller.onTick = { [weak self] tick, open in
            self?.refreshUI(tick: tick, sessionOpen: open)
        }

        setupMenu()
        poller.start()
    }

    public func applicationWillTerminate(_ notification: Notification) {
        poller?.stop()
    }

    private func makeClassifier(persona: String) throws -> Classifier {
        let pack = try RuleLoader.loadPack(persona: persona)
        let sensitive = try RuleLoader.loadSensitive()
        return Classifier(pack: pack, sensitive: sensitive)
    }

    private func setupMenu() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.title = "⚪️"

        let menu = NSMenu()
        stateLine.isEnabled = false
        totalsLine.isEnabled = false
        menu.addItem(stateLine)
        menu.addItem(totalsLine)
        menu.addItem(.separator())

        let personaMenu = NSMenu()
        for p in RuleLoader.personas {
            let item = NSMenuItem(title: p.capitalized, action: #selector(pickPersona(_:)),
                                  keyEquivalent: "")
            item.target = self
            item.representedObject = p
            item.state = (p == persona) ? .on : .off
            personaMenu.addItem(item)
            personaItems.append(item)
        }
        let personaRoot = NSMenuItem(title: "Persona", action: nil, keyEquivalent: "")
        menu.setSubmenu(personaMenu, for: personaRoot)
        menu.addItem(personaRoot)

        pauseItem.target = self
        menu.addItem(pauseItem)
        menu.addItem(.separator())
        let quit = NSMenuItem(title: "Quit FomiForMe", action: #selector(NSApplication.terminate(_:)),
                              keyEquivalent: "q")
        menu.addItem(quit)
        statusItem.menu = menu
    }

    private func refreshUI(tick: Tick, sessionOpen: Bool) {
        let icon: String
        let state: String
        if poller.paused {
            icon = "⏸"; state = "Paused"
        } else if sessionOpen {
            switch tick.category {
            case .work, .privateWork: icon = "🟢"; state = "In session — working"
            case .nonwork, .privateNonwork: icon = "🟠"; state = "In session — drifting"
            case .unknown: icon = "🟢"; state = "In session"
            }
        } else {
            icon = "⚪️"; state = "No session"
        }
        let totals = store.todayTotals(tickInterval: poller.tickIntervalS)
        statusItem.button?.title = icon
        stateLine.title = state
        totalsLine.title = String(format: "Today: %@ work · %@ non-work",
                                  Self.hm(totals.work), Self.hm(totals.nonwork))
    }

    @objc private func togglePause() {
        poller.setPaused(!poller.paused)
        pauseItem.title = poller.paused ? "Resume monitoring" : "Pause monitoring"
        statusItem.button?.title = poller.paused ? "⏸" : "⚪️"
        stateLine.title = poller.paused ? "Paused" : "No session"
    }

    @objc private func pickPersona(_ sender: NSMenuItem) {
        guard let p = sender.representedObject as? String else { return }
        guard let classifier = try? makeClassifier(persona: p) else { return }
        persona = p
        poller.setClassifier(classifier)
        for item in personaItems { item.state = (item.representedObject as? String == p) ? .on : .off }
    }

    private static func hm(_ seconds: Int) -> String {
        let h = seconds / 3600, m = (seconds % 3600) / 60
        return h > 0 ? "\(h)h \(m)m" : "\(m)m"
    }
}
