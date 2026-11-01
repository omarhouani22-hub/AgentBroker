# Clara LTX-2 + Google AI Studio experiment

This branch is an **isolated prototype**. It does not change the Flask app, production model routing, deployment, storage, or sales.

## LTX-2
`python -m experiments.clara_media_studio` prepares a reviewable video job using an approved Clara asset. **No MP4 is generated yet.** LTX-2 inference, GPU availability, output licensing, identity consistency and cost must be verified before an actual render integration. Owner approval is required before publication. No unverified AgentVault feature claims.

## Google AI Studio / Gemini
`experiments.clara_google_ai` prepares a Gemini REST request. The network call is disabled unless `CLARA_EXPERIMENT_GOOGLE_ENABLED=1` and `GEMINI_API_KEY` are set by the owner in a secure environment. The key must never be committed. The provider may have quota, billing and data-handling implications; confirm terms before enabling. No production fallback or automatic billing is introduced.

## Tests
`python -m unittest tests.test_clara_media_experiments`

## Next release gates
1. Verify local offline tests.
2. Obtain explicit owner approval to test a Gemini key or external LTX inference.
3. Confirm provider pricing, free quota and commercial usage rights.
4. Render one private 5-second Clara sample with an approved image and check face consistency.
5. Keep production deployment and sales on hold until independent backup, restore and persistence gates pass.

## Seven-second storyboard
Run `python -m experiments.clara_video_storyboard` to inspect a structured, three-shot script. It does not render or upload media.

## Validation status
Offline tests are committed but have **not yet been executed in a verified runner**. No Gemini key, LTX GPU or external model service has been connected. The draft PR remains unmerged and undeployed.
