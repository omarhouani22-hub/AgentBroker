import Foundation
import AVFoundation
import Speech

/// Native device voices and permission-gated dictation. No API keys or paid speech service.
final class NativeSpeech: NSObject, AVSpeechSynthesizerDelegate {
    private let emit: ([String: Any]) -> Void
    private let synthesizer = AVSpeechSynthesizer()
    private var spoken: [ObjectIdentifier: Int] = [:]
    private let engine = AVAudioEngine()
    private var task: SFSpeechRecognitionTask?
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var recognizer: SFSpeechRecognizer?
    private var recognitionID: Int?
    private var tapped = false
    private var finishing = false
    private var finalSent = false
    private var silence: Timer?
    private var deadline: Timer?
    private var finishDeadline: Timer?
    private var lastText = ""

    init(emit: @escaping ([String: Any]) -> Void) {
        self.emit = emit; super.init(); synthesizer.delegate = self
    }
    func handle(_ action: String, body: [String: Any]) {
        switch action {
        case "voices":
            emit(["type":"voices", "voices":AVSpeechSynthesisVoice.speechVoices().map { voice -> [String: Any] in
                let quality = voice.quality == .premium ? " Premium" : (voice.quality == .enhanced ? " Enhanced" : "")
                return ["name":voice.name + quality + (voice.gender == .female ? " Female" : ""), "lang":voice.language, "voiceURI":voice.identifier, "localService":true]
            }])
        case "speak":
            guard let id = body["id"] as? Int, let text = body["text"] as? String, !text.isEmpty, text.count <= 10000 else { return }
            guard spoken.count < 64 else { emit(["type":"speechError", "id":id, "error":"busy"]); return }
            do {
                let session = AVAudioSession.sharedInstance()
                try session.setCategory(.playback, mode: .spokenAudio)
                try session.setActive(true)
                let utterance = AVSpeechUtterance(string: text)
                let language = safeLanguage(body["language"] as? String)
                if let identifier = body["voice"] as? String,
                   let chosen = AVSpeechSynthesisVoice(identifier: identifier), chosen.language.prefix(2) == language.prefix(2) {
                    utterance.voice = chosen
                } else { utterance.voice = AVSpeechSynthesisVoice(language: language) }
                let speed = body["rate"] as? Double ?? 1
                let volume = body["volume"] as? Double ?? 1
                utterance.rate = AVSpeechUtteranceDefaultSpeechRate * Float(speed.isFinite ? min(1.4, max(0.6, speed)) : 1)
                utterance.volume = Float(volume.isFinite ? min(1, max(0, volume)) : 1)
                spoken[ObjectIdentifier(utterance)] = id; synthesizer.speak(utterance)
            } catch { emit(["type":"speechError", "id":id, "error":"audio-capture"]) }
        case "cancelSpeech": spoken.removeAll(); synthesizer.stopSpeaking(at: .immediate)
        case "resumeSpeech": synthesizer.continueSpeaking()
        case "recognize":
            guard let id = body["id"] as? Int else { return }
            startRecognition(id: id, language: safeLanguage(body["language"] as? String))
        case "finishRecognition":
            if body["id"] as? Int == recognitionID { finishInput() }
        case "abortRecognition":
            if body["id"] as? Int == recognitionID { endRecognition(error: nil) }
        default: break
        }
    }
    private func safeLanguage(_ value: String?) -> String { value?.hasPrefix("ar") == true ? "ar-JO" : "en-US" }
    func pause() {
        spoken.removeAll(); synthesizer.stopSpeaking(at: .immediate)
        endRecognition(error: "aborted")
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }
    private func startRecognition(id: Int, language: String) {
        endRecognition(error: "aborted"); recognitionID = id; finishing = false; finalSent = false; lastText = ""
        SFSpeechRecognizer.requestAuthorization { [weak self] status in
            DispatchQueue.main.async {
                guard let self, self.recognitionID == id else { return }
                guard status == .authorized else { self.endRecognition(error: "not-allowed"); return }
                AVAudioSession.sharedInstance().requestRecordPermission { [weak self] allowed in
                    DispatchQueue.main.async {
                        guard let self, self.recognitionID == id else { return }
                        guard allowed else { self.endRecognition(error: "not-allowed"); return }
                        self.beginInput(id: id, language: language)
                    }
                }
            }
        }
    }
    private func beginInput(id: Int, language: String) {
        let locales = SFSpeechRecognizer.supportedLocales().sorted { $0.identifier < $1.identifier }
        let normalized = { (locale: Locale) in locale.identifier.replacingOccurrences(of: "_", with: "-") }
        let locale = locales.first { normalized($0) == language }
            ?? locales.first { normalized($0) == (language.hasPrefix("ar") ? "ar-SA" : "en-US") }
            ?? locales.first { normalized($0).prefix(2) == language.prefix(2) }
        guard !finishing, let locale, let recognizer = SFSpeechRecognizer(locale: locale), recognizer.isAvailable else {
            endRecognition(error: "service-not-allowed"); return
        }
        self.recognizer = recognizer
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playAndRecord, mode: .measurement, options: [.defaultToSpeaker, .allowBluetooth])
            try session.setActive(true)
            let request = SFSpeechAudioBufferRecognitionRequest()
            request.shouldReportPartialResults = true
            if recognizer.supportsOnDeviceRecognition { request.requiresOnDeviceRecognition = true }
            self.request = request
            let input = engine.inputNode
            let format = input.outputFormat(forBus: 0)
            guard format.sampleRate > 0, format.channelCount > 0 else { endRecognition(error: "audio-capture"); return }
            input.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in request.append(buffer) }
            tapped = true
            task = recognizer.recognitionTask(with: request) { [weak self] result, error in
                DispatchQueue.main.async {
                    guard let self, self.recognitionID == id else { return }
                    if let result {
                        let text = String(result.bestTranscription.formattedString.prefix(2000))
                        let changed = text != self.lastText
                        self.lastText = text
                        if !self.finalSent {
                            self.finalSent = result.isFinal
                            self.emit(["type":"recognitionResult", "id":id, "text":text, "final":result.isFinal])
                        }
                        if result.isFinal { self.endRecognition(error: nil); return }
                        if changed { self.armSilence(seconds: 2.0) }
                    }
                    if error != nil { self.endRecognition(error: self.lastText.isEmpty ? "network" : nil) }
                }
            }
            engine.prepare(); try engine.start()
            emit(["type":"recognitionStart", "id":id]); armSilence(seconds: 7)
            deadline = Timer.scheduledTimer(withTimeInterval: 45, repeats: false) { [weak self] _ in self?.finishInput() }
        } catch { endRecognition(error: "audio-capture") }
    }
    private func armSilence(seconds: TimeInterval) {
        guard !finishing else { return }
        silence?.invalidate()
        silence = Timer.scheduledTimer(withTimeInterval: seconds, repeats: false) { [weak self] _ in
            guard let self else { return }
            if self.lastText.isEmpty { self.endRecognition(error: "no-speech") }
            else { self.finishInput() }
        }
    }
    private func stopEngine() {
        engine.stop()
        if tapped { engine.inputNode.removeTap(onBus: 0); tapped = false }
    }
    private func finishInput() {
        guard recognitionID != nil, !finishing else { return }
        finishing = true; silence?.invalidate(); deadline?.invalidate(); stopEngine(); request?.endAudio()
        finishDeadline = Timer.scheduledTimer(withTimeInterval: 3, repeats: false) { [weak self] _ in
            // Preserve partial text for explicit review; never call it a final result.
            self?.endRecognition(error: nil)
        }
    }
    private func endRecognition(error: String?) {
        let id = recognitionID; recognitionID = nil
        silence?.invalidate(); silence = nil; deadline?.invalidate(); deadline = nil; finishDeadline?.invalidate(); finishDeadline = nil
        stopEngine(); request?.endAudio(); task?.cancel(); task = nil; request = nil; recognizer = nil
        guard let id else { return }
        if let error { emit(["type":"recognitionError", "id":id, "error":error]) }
        emit(["type":"recognitionEnd", "id":id])
    }
    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didStart utterance: AVSpeechUtterance) {
        if let id = spoken[ObjectIdentifier(utterance)] { emit(["type":"speechStart", "id":id]) }
    }
    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        if let id = spoken.removeValue(forKey: ObjectIdentifier(utterance)) { emit(["type":"speechEnd", "id":id]) }
    }
    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didCancel utterance: AVSpeechUtterance) {
        if let id = spoken.removeValue(forKey: ObjectIdentifier(utterance)) { emit(["type":"speechError", "id":id, "error":"canceled"]) }
    }
}
