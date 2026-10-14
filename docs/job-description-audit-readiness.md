# Job Description Audit — checkout and delivery readiness

Status: **NOT READY FOR AUTOMATED PAID ORDERS**. This is a code-level audit; no real payment or delivery was tested.

## Verified in app.py
- Public GET `/services/job-description-audit` exists and is exempt from the operator authentication gate.
- Contact button is shown only if `SALES_CONTACT_EMAIL` is syntactically valid.
- Payment button is shown only if `JD_AUDIT_PAYMENT_URL` is an HTTPS URL without embedded credentials. This is an outbound link, **not** a verified payment integration.
- If neither setting is configured, the page says ordering is being set up.
- POST `/offers/jd-audit/draft` is operator-protected, validates title/description and requires a configured model. Its output explicitly requires human review.
- No public order-submission or document-upload endpoint was identified in the inspected offer flow.
- No payment webhook signature verification, order/payment state machine, or confirmed-payment-to-delivery path was identified in the inspected offer flow.

## Acceptance criteria before taking real payments
1. Choose supported checkout provider and publish an approved price, currency, refund terms, deliverables and realistic turnaround.
2. Create unique order IDs; collect minimum necessary contact details and job-description text/document safely. Validate file types and size; avoid unnecessary personal data.
3. Verify payments server-side with provider signatures/API, amounts and currencies; handle replay, duplicate callbacks, failures and refunds. Never accept a browser redirect as proof of payment.
4. Queue analysis only after verified payment; store order and processing status durably (not solely on Render free ephemeral disk).
5. Produce a reviewable draft with clear limits; require human approval before sending any report.
6. Deliver securely to the verified purchaser; log consent and delivery status without leaking confidential job descriptions.
7. Run end-to-end sandbox tests for success, failed payment, replay, duplicate event, timeout, refund, and delivery failure.
8. Do not claim autonomous sales, accept live payments, or change Render payment credentials before the above checks pass.

## Safe next implementation
Build a no-payment **intake preview** with input validation and privacy warnings, protected against spam, plus tests. Keep checkout disabled until provider, pricing and approval are finalized.

## Current verification status (2026-10-14)
- Added negative tests for malformed JSON, title length and absence of checkout without configuration.
- The contract test suite uses a mocked model; it does not measure live output quality or prove delivery readiness.
- No payment or public upload should be activated from this branch.
- Operator can use the synthetic sample loader on main once the latest Render deployment is confirmed live.
