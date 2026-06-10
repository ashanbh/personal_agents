import Foundation

/// Persona rule pack (T0). JSON files live in Sources/FomiForMe/Rules/.
public struct RulePack: Codable {
    public var persona: String
    public var workBundlePrefixes: [String]
    public var nonworkBundlePrefixes: [String]
    public var workDomainSuffixes: [String]
    public var nonworkDomainSuffixes: [String]
    public var workAppSubstrings: [String]
    public var nonworkAppSubstrings: [String]
    public var meetingBundlePrefixes: [String]
    /// Doctor persona: bundle prefixes for which screen frames must never be
    /// captured (M2+). Metadata-only mode. Unused in M1 but part of the contract.
    public var metadataOnlyBundlePrefixes: [String]?
}

/// Global sensitive map. Matches collapse to `private-*` BEFORE persistence.
public struct SensitiveMap: Codable {
    public var privateDomainSuffixes: [String]
    public var privateBundlePrefixes: [String]
    public var privateAppSubstrings: [String]
}

public enum RuleLoader {
    public static let personas = ["engineer", "accountant", "doctor"]

    public static func loadPack(persona: String, from dir: URL? = nil) throws -> RulePack {
        let data = try read(name: persona, dir: dir)
        return try JSONDecoder().decode(RulePack.self, from: data)
    }

    public static func loadSensitive(from dir: URL? = nil) throws -> SensitiveMap {
        let data = try read(name: "sensitive", dir: dir)
        return try JSONDecoder().decode(SensitiveMap.self, from: data)
    }

    private static func read(name: String, dir: URL?) throws -> Data {
        if let dir = dir {
            return try Data(contentsOf: dir.appendingPathComponent("\(name).json"))
        }
        guard let url = Bundle.module.url(forResource: name, withExtension: "json",
                                          subdirectory: "Rules") else {
            throw NSError(domain: "FomiForMe", code: 1, userInfo: [
                NSLocalizedDescriptionKey: "Rule file \(name).json not found in bundle"])
        }
        return try Data(contentsOf: url)
    }
}
