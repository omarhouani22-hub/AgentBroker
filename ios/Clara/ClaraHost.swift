import SwiftUI
import WebKit
import UIKit

struct SharedFile: Identifiable { let id = UUID(); let url: URL }

private final class ClaraMessageHandler: NSObject, WKScriptMessageHandler {
    weak var host: ClaraHost?
    init(_ host: ClaraHost) { self.host = host }
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        host?.userContentController(userContentController, didReceive: message)
    }
}

final class ClaraHost: NSObject, ObservableObject, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler, WKDownloadDelegate {
    static let home = ClaraURLPolicy.home
    @Published var failure: String?
    @Published var download: SharedFile?
    var enabled = false
    private var loaded = false
    private var pendingFiles: [ObjectIdentifier: URL] = [:]
    private lazy var speech = NativeSpeech { [weak self] event in self?.emit(event) }
    lazy var webView: WKWebView = {
        let controller = WKUserContentController()
        controller.add(ClaraMessageHandler(self), name: "clara")
        if let url = Bundle.main.url(forResource: "NativeBridge", withExtension: "js"),
           let source = try? String(contentsOf: url, encoding: .utf8) {
            controller.addUserScript(WKUserScript(source: source, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        }
        let config = WKWebViewConfiguration()
        config.userContentController = controller
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []
        let view = WKWebView(frame: .zero, configuration: config)
        view.navigationDelegate = self; view.uiDelegate = self
        view.isOpaque = false; view.backgroundColor = .clear
        view.scrollView.backgroundColor = UIColor(red: 0.055, green: 0.078, blue: 0.137, alpha: 1)
        view.allowsBackForwardNavigationGestures = false
        return view
    }()

    private func trusted(_ url: URL?) -> Bool {
        ClaraURLPolicy.trusted(url)
    }
    func loadIfNeeded() { if !loaded { load() } }
    func load() {
        guard enabled else { return }
        failure = nil; loaded = true
        webView.load(URLRequest(url: Self.home))
    }
    func pause() {
        enabled = false; speech.pause()
        webView.evaluateJavaScript("window.ClaraNativeSpeech?._suspend();")
        if #available(iOS 15.0, *) {
            webView.setCameraCaptureState(.none)
            webView.setMicrophoneCaptureState(.none)
        }
    }
    private func emit(_ event: [String: Any]) {
        guard trusted(webView.url), let data = try? JSONSerialization.data(withJSONObject: event),
              let json = String(data: data, encoding: .utf8) else { return }
        webView.evaluateJavaScript("window.ClaraNativeSpeech?._receive(\(json));")
    }
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        let origin = message.frameInfo.securityOrigin
        guard enabled, message.frameInfo.isMainFrame, origin.protocol == "https", origin.host == Self.home.host,
              (origin.port == 0 || origin.port == 443), trusted(webView.url),
              let body = message.body as? [String: Any], let action = body["action"] as? String else { return }
        speech.handle(action, body: body)
    }
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        let url = action.request.url
        let localBlob = ClaraURLPolicy.blobDownload(url, page: webView.url)
        guard trusted(url) || (localBlob && trusted(webView.url)) else { decisionHandler(.cancel); return }
        if ClaraURLPolicy.documentDownload(url), action.targetFrame?.isMainFrame == true {
            decisionHandler(.download); return
        }
        if action.shouldPerformDownload { decisionHandler(.download); return }
        guard trusted(url), action.targetFrame?.isMainFrame == true, url?.path.hasPrefix("/clara/") == true else {
            decisionHandler(.cancel); return
        }
        decisionHandler(.allow)
    }
    func webView(_ webView: WKWebView, decidePolicyFor response: WKNavigationResponse, decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void) {
        decisionHandler(response.canShowMIMEType ? .allow : .download)
    }
    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) { speech.pause() }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        failure = nil
        if enabled && trusted(webView.url) { speech.handle("voices", body: [:]) }
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        if (error as NSError).code != NSURLErrorCancelled { failure = "Clara needs an internet connection. Check your connection and try again."; loaded = false }
    }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        didFail(error)
    }
    private func didFail(_ error: Error) { failure = "The page could not load. Please try again."; loaded = false }
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) { loaded = false; failure = "Clara needs to reload." }
    func webView(_ webView: WKWebView, requestMediaCapturePermissionFor origin: WKSecurityOrigin, initiatedByFrame frame: WKFrameInfo, type: WKMediaCaptureType, decisionHandler: @escaping (WKPermissionDecision) -> Void) {
        let allowed = enabled && frame.isMainFrame && origin.protocol == "https" && origin.host == Self.home.host && (origin.port == 0 || origin.port == 443) && trusted(webView.url)
        decisionHandler(allowed ? .prompt : .deny)
    }
    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) { download.delegate = self }
    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) { download.delegate = self }
    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String, completionHandler: @escaping (URL?) -> Void) {
        guard enabled else { completionHandler(nil); return }
        let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        do {
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            let name = URL(fileURLWithPath: suggestedFilename).lastPathComponent
            let destination = directory.appendingPathComponent(name.isEmpty ? "Clara-document" : name)
            pendingFiles[ObjectIdentifier(download)] = destination; completionHandler(destination)
        } catch { completionHandler(nil) }
    }
    func downloadDidFinish(_ download: WKDownload) {
        let file = pendingFiles.removeValue(forKey: ObjectIdentifier(download))
        if enabled, let url = file { self.download = SharedFile(url: url) }
    }
    func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {
        pendingFiles.removeValue(forKey: ObjectIdentifier(download))
        failure = "The file could not be downloaded. Please try again."
    }
}

struct ClaraWebView: UIViewRepresentable {
    let host: ClaraHost
    func makeUIView(context: Context) -> WKWebView { host.webView }
    func updateUIView(_ uiView: WKWebView, context: Context) {}
}
struct FileShare: UIViewControllerRepresentable {
    let url: URL
    func makeUIViewController(context: Context) -> UIActivityViewController { UIActivityViewController(activityItems: [url], applicationActivities: nil) }
    func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}
