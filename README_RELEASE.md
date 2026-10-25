# ACTCalc production release candidate — 24 October 2026

**STATUS: NO-GO for public activation from this session.** The release package has been rebuilt, strengthened and locally tested, but live hosting credentials, actual SMTP delivery, verified legal operator information and the ability to update the existing actcalc.com hosting project are not available in this environment. No claim is made that this package is deployed to actcalc.com.

## What's built

- Mobile-optimized ACTCalc Rev3 user workspace with the user's existing engineering calculation engine, local saved work, unit conversion, graphs, Excel/CSV/JSON downloads, and draggable/persistent workspace controls.
- Fixed phone contact entry point, clearer download-versus-send wording, actual same-origin contact endpoint, valid PWA manifest/icons/service worker (network-first HTML to reduce stale versions), privacy and engineering-limitations pages.
- FastAPI deployment service: request validation, one-use HMAC CSRF/anti-spam nonce bound to direct-client address, honeypot, server-side SQLite queue, 30-day purge, administrator-only inbox and deletion, SMTP delivery worker with exponential-backoff retry and terminal operator-visible failures, replay protection, input-size limits, basic connection rate limiting, security headers with inline script hashes, no permissive cross-origin policy.
- Fail-closed public release gate. `ACTCALC_PUBLIC=true` alone **never** makes an incompletely configured service public. Four additional verification flags stay false until the legal, SMTP, backup-restore, and real-device checks are actually completed.
- Docker image/Compose plus persistent `/data` volume, health endpoint, verification script and automated tests. The Docker configuration was inspected but no Docker daemon is available in this environment for a real image-build test.
- Non-overwriting SQLite snapshot backup and restore-as-new tools (`backend.backup`) with WAL consistency, integrity checking, and filesystem owner-only permissions. Tested with representative records.
- Corrected exact release identifier used by post-deploy verification, metadata canonical URL, and social image to an actually served brand icon.

## Local development

Requirements: Python 3.13+ (tested with compatible installed Python), dependencies in `requirements.txt` and `dev-requirements.txt`.

```
python -m pip install -r dev-requirements.txt
export ACTCALC_CONTACT_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export ACTCALC_ADMIN_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export ACTCALC_DB_PATH=/data/actcalc.sqlite3
ACTCALC_PUBLIC=false ACTCALC_ALLOW_LOCAL_DEV=true python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
PYTHONPATH=. pytest -q tests/test_backend.py
PYTHONPATH=. python tests/qa_browser.py
```

In a local environment `/data` must be writable. A development-only database elsewhere may be used for private tests. **Never set ACTCALC_ALLOW_LOCAL_DEV=true on a publicly reachable host.** The release server defaults to 503 for visitors until the gate is complete.

## Production launch checklist (operator controlled)

1. **Hosting:** Deploy the Docker service to a host supporting persistent storage and background work. The existing ChatGPT Sites deployment is not equivalent to a Python/ASGI backend. A static HTML upload by itself will NOT make the contact form work. Use a verified release host and connect `actcalc.com`/`www.actcalc.com` after the platform supports those custom domains. Preserve the domain origin so local saved works are not unnecessarily lost. Back up the old site and keep rollback available.
2. **Secrets:** Add two DIFFERENT strong, stable secrets `ACTCALC_CONTACT_SECRET` and `ACTCALC_ADMIN_TOKEN` as host secrets, plus verified SMTP host, port, user, password, sender and recipient. Do not put secrets in frontend JS, in a git repository, or in ChatGPT messages. Use `ACTCALC_DB_PATH=/data/actcalc.sqlite3` backed by a persistent, regularly backed up disk.
3. **Legal:** Enter the real legal operator name and privacy email (`ACTCALC_OPERATOR_NAME`, `ACTCALC_PRIVACY_EMAIL`), then review and finalise `/privacy` and `/terms` to match the actual operator, jurisdiction, vendors, hosting and business practices. Current pages explicitly flag required review and are **not** approved legal templates. Do not invent an operator name or contact information.
4. **Proxy:** Put the service behind HTTPS, forward only authenticated/trusted proxy headers, pin allowed hosts, restrict administrator-token access, collect appropriate operational metrics (without collecting customer calculations), test failure recovery, and configure backups and restore. Ensure the actual trusted proxy/IP design allows accurate rate limiting. Ensure a secure method to reach the operator inbox.
5. **Verify:** Confirm that `/api/health` returns `public_release_configuration_ready: true`. Test actual SMTP delivery to the operator, response to the sender, database persistence across host restart, backup and restore, mobile iOS Safari and Android Chrome, working contact form on a real device, download formats (particularly XLSX round trip), updated service worker/PWA, accessible control interactions and HTTPS for both domains. Then run `python deploy/verify_live.py https://actcalc.com` and test on the real production URL. Always check the final host's privacy/auth setting rather than relying on local tests.
6. **Activate:** Only once all checks above pass, set `ACTCALC_LEGAL_REVIEW_CONFIRMED=true`, `ACTCALC_SMTP_DELIVERY_VERIFIED=true`, `ACTCALC_BACKUP_RESTORE_VERIFIED=true`, `ACTCALC_LIVE_DEVICE_VERIFIED=true`, and `ACTCALC_PUBLIC=true`, deploy, verify availability under production HTTPS, and change the hosting project's access policy from private to public. Verify as a logged-out external visitor. If any critical test fails, set `ACTCALC_PUBLIC=false` / restore old private hosting and investigate before retrying.

## Operations

```
python -m backend.manage check    # fails readiness if operator or infrastructure is incomplete
python -m backend.manage inbox    # print recent contact messages in a restricted operator terminal
python -m backend.manage send     # retry queued SMTP deliveries
python -m backend.manage purge    # remove messages older than 30 days
python -m backend.manage backup /data/backups/actcalc-YYYYMMDD.sqlite3
python -m backend.manage verify-backup /data/backups/actcalc-YYYYMMDD.sqlite3
python -m backend.manage restore-as-new /data/backups/actcalc-YYYYMMDD.sqlite3 /data/restored-YYYYMMDD.sqlite3
```

For API inbox: authenticated `GET /api/admin/messages` and `DELETE /api/admin/messages/{id}` with `Authorization: Bearer <ACTCALC_ADMIN_TOKEN>`; never embed this token in the site. Backend contact results show **received and queued**, not an unverified claim of email delivery. SMTP errors must be monitored operationally. Failed deliveries back off exponentially and move to `failed` after ten attempts rather than retrying indefinitely. The restricted operator inbox shows status and attempt count. Backups contain personal contact information: use encrypted, access-restricted off-host storage and a deletion schedule aligned with the actual privacy notice. Restore-as-new never overwrites the active database; stop the app and separately approve the path switch after verifying restore integrity.

## Latest offline release checks (24 October 2026)

- `PYTHONPATH=. pytest -q tests/test_backend.py tests/test_backup.py tests/test_release_ops.py`: **18 passed**. Includes synthetic production-origin requests on both domains, restart persistence, CSV-compatible contact storage, safe retry behavior, old-schema migration, SQLite WAL backup, restore-as-new and fail-closed readiness.
- `PYTHONPATH=. python tests/qa_browser.py`: passed at **320, 390, 768, 1024 and 1440 px** in Chromium, including Math, graph, unit conversion, Functions navigation and a fully mocked (non-transmitting) mobile Contact form.
- Parsed **44 inline scripts** with `node --check`: **zero syntax failures**.
- A real HTTP development API started and replied to `/api/health`, but Chromium navigation to localhost and the real domain was blocked by the test environment. Hence browser testing does not prove the actual live origin or cross-browser mobile support.
- This package **has NOT** been pushed to the existing actcalc.com project. Neither SMTP transport nor DNS/TLS status can be verified here. Public status is intentionally NO-GO.

## Verification scope / limitations

- Backend API testing: security gates, HMAC validation, replay, CSRF, persistence across restart, rate limits, admin access, deletion, 30-day retention, mocked SMTP worker and backoff.
- Chromium UI testing: real rendered application via HTML injection at multiple widths, math calculation, graph, units, functions, no page errors, no horizontal overflow, and visible mobile Contact plus mocked browser submission. Browser navigation to localhost was denied by this environment; this is **not a live domain test**.
- Browser saved calculations remain **local to the user's browser**, not synchronized across devices. A browser-storage or PWA migration across different origins requires a documented export/import plan.
- The engineering engine is unchanged. Representative arithmetic, graph and unit workflows were exercised; every specialized engineering equation has not been independently qualified to a design-code standard. Do not market as a certified safety engineering product.
- Actual SMTP credentials, legal operator details, external host access and public publishing controls are absent from this environment. No user account or payment system exists or is implied.

## Launch decision

Release candidate built, backend functional locally, standard smoke tests passed. **Public launch blocked** until live-domain integration, SMTP, legal/operator and external-browser verification are complete. Preserve the existing private actcalc.com site until then.

## GitHub/Render preview update

This GitHub package adds a private Basic Auth staging preview (`preview` username, generated `ACTCALC_PREVIEW_TOKEN` password in Render). The preview does not change `ACTCALC_PUBLIC` or bypass any production-readiness flags. Use HTTPS only. Never disclose the preview token in tickets, repositories, browser URLs, or chat. Unauthenticated visitors receive HTTP 401 while preview is configured, or HTTP 503 when no preview credential exists. After production review, change the public gate only after all checks pass.
