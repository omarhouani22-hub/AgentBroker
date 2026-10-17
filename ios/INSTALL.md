# Clara — private iPhone app

This is an iPhone app project, not an App Store release. It connects to your existing Clara service at https://agentbroker-jayk.onrender.com/clara/. It needs internet. The source contains no owner password, model API key, private profile or signing certificate.

## What is included

- Native SwiftUI app with the existing Clara conversation interface inside WKWebView.
- Native iPhone speech playback and English/Arabic dictation. Available voices depend on your phone; downloaded enhanced female voices are preferred. This does not reproduce ChatGPT's voice.
- Face ID or device passcode before opening, and relocking after backgrounding. A device passcode is required. Clara's existing website sign-in is still required inside the app.
- Camera preview only when requested, document uploads, and a native share sheet for downloaded copies. Nothing is sent to another person automatically.
- Native operations restricted to the exact HTTPS Clara origin and its main frame. Microphone, camera and speech permissions remain explicit iOS prompts.
- No paid speech API is enabled, no App Store publication, no account creation, and no background recording.

The server and model providers still process the messages you send, as in the website. Dictation uses on-device recognition when supported and otherwise may use Apple's service. Website updates continue to appear in the app. This is not a fully offline assistant or a guarantee of permanent server-side memory.

## Install on your iPhone with a Mac

1. Install Xcode from Apple. Open `Clara.xcodeproj` in this folder.
2. In Xcode → Settings → Accounts, sign in to your own Apple Account. Never put the Apple password or signing credentials in this repository or chat.
3. Select the Clara target → Signing & Capabilities → your Personal Team. If the bundle ID is unavailable, change `com.omarhourani.clara` to a unique ID you control.
4. Connect your iPhone to the Mac, trust the computer if prompted, and enable Developer Mode when iOS asks.
5. Select your iPhone as the run destination and press Run. Complete Apple's normal signing/trust prompts on your own devices.
6. Unlock Clara with Face ID/passcode, sign into your existing Clara space, then grant microphone/speech/camera only when you use them.

Apple's free Personal Team provisioning is temporary (normally 7 days); you need to rebuild/reinstall after it expires. This route does not require purchasing Apple Developer Program membership. Apple's terms and restrictions apply: https://developer.apple.com/help/account/basics/about-your-developer-account

There is no signed IPA in this project. `Clara-iPhone-UNSIGNED.zip` is a build-check output and cannot be installed by tapping it on an iPhone. The source ZIP is for Xcode. With only an iPhone and no signing route, use the existing home-screen web app while arranging installation; do not treat that as a native app download.

## Verify the project

The `Clara private iPhone app` GitHub workflow checks the JavaScript adapter, native URL policy, simulator compilation, device compilation without signing, and simulator launch. It uploads source and unsigned build artifacts. This does not test a real iPhone's microphone, camera, Face ID or actual voice availability; those must be checked on the owner's device after signing.

## On-device acceptance check

Open/lock/reopen the app. Start a call and confirm the English greeting. Try English and Arabic dictation separately using the input-language selector; review partial transcripts before sending. End the call and confirm the microphone stops. Background the app and confirm it locks and stops audio. Open Camera, attach one still, and send only if you want that image processed. Upload a test document and save an edited copy through the share sheet. If dictation permission is denied, enable it in iPhone Settings; text chat remains available.
