import SwiftUI
import LocalAuthentication

@main
struct ClaraApp: App {
    @StateObject private var host = ClaraHost()
    @Environment(\.scenePhase) private var phase
    @State private var unlocked = false
    @State private var unlocking = false
    @State private var lockMessage = "Unlock with Face ID or your device passcode."

    var body: some Scene {
        WindowGroup {
            ZStack {
                Color(red: 0.055, green: 0.078, blue: 0.137).ignoresSafeArea()
                ClaraWebView(host: host).opacity(unlocked ? 1 : 0).allowsHitTesting(unlocked)
                if !unlocked {
                    VStack(spacing: 20) {
                        Image(systemName: "lock.shield").font(.system(size: 42))
                        Text("Clara").font(.largeTitle.bold())
                        Text(lockMessage).multilineTextAlignment(.center)
                        Button("Unlock Clara", action: unlock).buttonStyle(.borderedProminent).disabled(unlocking)
                    }.foregroundStyle(.white).padding(32)
                } else if let message = host.failure {
                    VStack(spacing: 18) {
                        Text(message).multilineTextAlignment(.center)
                        Button("Try again") { host.load() }.buttonStyle(.borderedProminent)
                    }.padding(28).background(.regularMaterial).clipShape(RoundedRectangle(cornerRadius: 20))
                }
            }
            .preferredColorScheme(.dark)
            .task { unlock() }
            .onChange(of: phase) { next in
                if next == .background { unlocked = false; host.pause() }
            }
            .sheet(item: $host.download) { item in FileShare(url: item.url) }
        }
    }

    private func unlock() {
        guard !unlocking, !unlocked else { return }
        unlocking = true
        let context = LAContext()
        var error: NSError?
        guard context.canEvaluatePolicy(.deviceOwnerAuthentication, error: &error) else {
            unlocking = false
            lockMessage = "Set a device passcode in iPhone Settings, then unlock Clara."
            return
        }
        context.evaluatePolicy(.deviceOwnerAuthentication, localizedReason: "Open your private Clara assistant") { success, _ in
            DispatchQueue.main.async {
                unlocking = false; unlocked = success
                host.enabled = success
                if success { host.loadIfNeeded() }
                else { lockMessage = "Clara is locked. Tap Unlock Clara to try again." }
            }
        }
    }
}
