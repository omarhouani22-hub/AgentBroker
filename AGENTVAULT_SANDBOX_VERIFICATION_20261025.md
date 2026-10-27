# AgentVault real PayPal Sandbox verification — 25 October 2026

Completed using the existing Sandbox Default Application and a real Sandbox buyer session. No mocks were used for PayPal create, approval, GET or capture. No real money or Live payment was captured.

- Order: `21632567BS9794226`
- Capture: `9ET50408115101211`
- Provider order and capture status: `COMPLETED`
- Amount: USD 5.00 (Sandbox virtual funds)
- Sandbox merchant: `JRGM3Z2BYZXP4`
- Actual AgentVault POST /v1/vaults and POST /v1/orders routes ran with TESTING=true and a new isolated local SQLite database, generated test-only encryption key, Sandbox credentials and test-only sales/recovery flags. Production flags and database were untouched.
- Unpaid checkpoint write was rejected (402).
- Browser buyer approval was confirmed by provider GET status APPROVED before capture.
- Actual POST /v1/orders/<id>/capture returned activated=true; provider GET later returned COMPLETED with the capture above.
- Exactly one vault, one order and one checkpoint existed in the isolated database, with exactly one payment_activated audit event.
- Repeating the capture route returned already_completed=true and left entitlement expiration unchanged.
- Checkpoint save succeeded; a newly constructed application recovered byte-identical data with SHA-256 `7578118ea4ad07699287679feb2e600b204b86d30d04234b5932b3877170693a`.
- Temporary API credentials were transferred encrypted using RSA-OAEP SHA-256, used only in process memory; the temporary private transport key was removed. No login passwords were read/copied/entered by the agent. No production keys were copied.

This proves the service payment/activation/save/restore/idempotency path against real PayPal Sandbox, with isolated local SQLite. It does not prove hosted PostgreSQL concurrency, production backup plus original-key recovery, refunds/reversals, Live settlement eligibility, or Live payment capture. SALES_ENABLED and RECOVERY_VERIFIED remain false in production. Commercial readiness is not claimed.
