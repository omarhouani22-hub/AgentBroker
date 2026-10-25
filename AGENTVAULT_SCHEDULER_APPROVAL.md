# AgentVault remaining launch checks — 25 October 2026

## Actual Sandbox refund

Provider API confirmed original Sandbox capture `9ET50408115101211` was COMPLETED, USD 5.00, expected merchant, original order `21632567BS9794226`. A full Sandbox-only refund returned ID `6PS40567H31921919`, status COMPLETED, USD 5.00. No Live refund/payment or production vault change occurred. Automatic approval review rejected polling the already running test output because it considered another refund possible. The refund was not repeated or bypassed. Further live-provider reconciliation/export assertions from that process were not retrieved and are not claimed as verified. Mocked refund/hold regression tests pass separately. Temporary transfer key and script were removed.

## Read-only merchant check

Secure merchant login/verification succeeded. The authenticated PayPal business dashboard showed no visible account-limitation banner. Account limits at https://www.paypal.com/unifiedsettings/liftLimits showed Receiving limit: Daily No limit and Balance limit: Daily No limit. No Lift Limits action, bank/account change, Live payment or settlement was performed. This is positive account-screen evidence, not proof that a particular Live payment will settle or avoid a later provider hold.

## Scheduler ready for owner access approval

39 isolated unit tests and three actual PostgreSQL integration tests passed in GitHub Actions run 40165772034. New internal operations endpoints default to disabled without AGENTVAULT_OPERATIONS_TOKEN. They accept one narrow token for: encrypted five-table data backup; one least-recently-reviewed paid-order status check; expired-data maintenance. They never return PayPal/DB/encryption credentials, create/capture/refund payments, grant paid access, or turn on sales. Backup excludes the encryption key and is Fernet-encrypted with the existing owner-held application key.

The proposal deployment-proposals/agentvault-operations.yml is NOT active. It proposes daily encrypted backups (00:17 UTC), maintenance only after artifact upload succeeds, hourly bounded payment review, 14-day artifact retention and a 16 MiB archive transfer ceiling. The repository is public, so encrypted artifacts must be treated as potentially publicly downloadable. The owner key stays outside GitHub. Standard public runners are free, but artifact storage has a shared quota; check existing storage and enforce zero paid usage before activation. GitHub schedules can be delayed/disabled and are not an SLA or backup monitoring replacement.

Activation requires owner approval to create a narrow token, store it in the existing Render service and repository Actions Secrets, install the workflow on default branch main and enable its repository variable. Do not copy database/PayPal/master-key secrets to Actions. Do not change paid plans, enable billing, turn on sales/recovery flags, or claim scheduler execution until a manual run and offsite download/restore verification pass.


## Read-only provider follow-up and disabled endpoint deployment — 25 October 2026

A separate read-only PayPal adapter explicitly forbidding create/capture/refund
API mutations retrieved the original Sandbox order with capture status REFUNDED.
Actual reconcile_payments using provider GET responses (not mocked responses)
created exactly one payment hold in a fresh isolated local SQLite fixture. Writes
returned 403, export preserved identical bytes, active=false and payment_review_required=true.
Repeated reconciliation added no new hold. The fixture represented the already-paid
original order; it did not repeat the earlier checkout/activation. No production
data or payment state changed during this follow-up. This safely resolves the
unretrieved reconciliation assertions from the first refund process without any
additional refund. Temporary transport files were removed.

Deploy dep-dbepb2ks728c73cqglcg (d2e3f98e57970f13a589fb860722537696d57fc4) reached live.
Fresh HTTP checks: /healthz 200 healthy durable storage, /v1/plans 200 with sales
false, POST /internal/operations/backup 503 operations_not_configured. No operations
token was created or shared; GitHub workflow remains a proposal and is not enabled.
39 unit tests and three PostgreSQL integration tests passed. Owner approval of the
specific new scoped scheduler access is still required, along with zero-cost
quota/budget verification, before enabling and testing scheduled execution.
