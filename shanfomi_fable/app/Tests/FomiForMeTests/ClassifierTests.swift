import XCTest
@testable import FomiForMe

final class ClassifierTests: XCTestCase {
    func makeClassifier(persona: String = "engineer") throws -> Classifier {
        Classifier(pack: try RuleLoader.loadPack(persona: persona),
                   sensitive: try RuleLoader.loadSensitive())
    }

    func testEngineerVSCodeIsWork() throws {
        let c = try makeClassifier()
        let t = c.classify(bundleId: "com.microsoft.VSCode", appName: "Code", domain: nil)
        XCTAssertEqual(t.category, .work)
        XCTAssertEqual(t.tier, 0)
    }

    func testInstagramDomainIsNonwork() throws {
        let c = try makeClassifier()
        let t = c.classify(bundleId: "com.apple.Safari", appName: "Safari",
                           domain: "instagram.com")
        XCTAssertEqual(t.category, .nonwork)
    }

    func testMeetingIsWork() throws {
        let c = try makeClassifier()
        let t = c.classify(bundleId: "us.zoom.xos", appName: "zoom.us", domain: nil)
        XCTAssertEqual(t.category, .work)
    }

    func testSensitiveCollapsesAndStripsIdentifiers() throws {
        let c = try makeClassifier()
        let t = c.classify(bundleId: "com.apple.Safari", appName: "Safari",
                           domain: "pornhub.com")
        XCTAssertEqual(t.category, .privateNonwork)
        XCTAssertNil(t.bundleId)
        XCTAssertNil(t.appName)
        XCTAssertNil(t.domain)
    }

    func testAccountantBankIsWorkNotSensitive() throws {
        let c = try makeClassifier(persona: "accountant")
        let t = c.classify(bundleId: "com.apple.Safari", appName: "Safari",
                           domain: "chase.com")
        XCTAssertEqual(t.category, .work)
    }

    func testBrowserWithoutDomainIsUnknown() throws {
        let c = try makeClassifier()
        let t = c.classify(bundleId: "com.google.Chrome", appName: "Google Chrome", domain: nil)
        XCTAssertEqual(t.category, .unknown)
    }

    func testSubdomainSuffixMatch() throws {
        let c = try makeClassifier()
        let t = c.classify(bundleId: "com.apple.Safari", appName: "Safari",
                           domain: "gist.github.com")
        XCTAssertEqual(t.category, .work)
    }
}
