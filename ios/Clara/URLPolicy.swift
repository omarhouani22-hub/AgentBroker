import Foundation

enum ClaraURLPolicy {
    static let home = URL(string: "https://agentbroker-jayk.onrender.com/clara/")!
    static func trusted(_ url: URL?) -> Bool {
        guard let url else { return false }
        return url.scheme == "https" && url.host == home.host && (url.port == nil || url.port == 443) && url.user == nil && url.password == nil
    }
    static func documentDownload(_ url: URL?) -> Bool {
        trusted(url) && url?.path.range(of: "^/companion/files/[A-Za-z0-9_-]+/download$", options: .regularExpression) != nil
    }
    static func blobDownload(_ url: URL?, page: URL?) -> Bool {
        trusted(page) && url?.absoluteString.hasPrefix("blob:https://agentbroker-jayk.onrender.com/") == true
    }
}
