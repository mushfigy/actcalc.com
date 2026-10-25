# ACTCalc — Engineering calculator

Complete local-first ACTCalc application with an HTTPS backend for contact requests. This repository is **not publicly live** by itself. Engineering inputs stay in each visitor's browser; only contact messages are stored server-side.

## GitHub to Render (secure release path)

1. Upload the contents of this repository to a **private GitHub repository** (not the ZIP as a single file). Do not upload `.env`, credentials or user data. GitHub Actions automatically tests the release on every `main` push.
2. Connect that GitHub repository to **Render**, then choose **New → Blueprint**, using `render.yaml`. This blueprint intentionally specifies a **paid Starter web service + persistent disk**, because SQLite would be erased on free Render instances. **Review any resulting charges before creating it.** CI must pass before deploy. Render deploys it behind a separate password-protected preview (HTTP Basic username `preview`, password `ACTCALC_PREVIEW_TOKEN` stored in Render), while `ACTCALC_PUBLIC=false`. The preview credential is never committed to GitHub.
3. In Render's protected environment settings, provide operator identity, privacy contact, SMTP details and verified sender address. Two separate secrets are generated automatically. Never place secrets in GitHub or this ZIP. Complete GDPR/privacy/terms operator review.
4. Use the password-protected Render preview to test an actual SMTP email, backup and restore of the production disk, and iOS/Android browsers. Verify the current domain's DNS and record a rollback. Only after success, change the four verification flags to `true`, change `ACTCALC_PUBLIC` to `true` in `render.yaml`, verify in a staging domain, then move `actcalc.com`/`www.actcalc.com` from the current host to the verified service, with DNS/TLS checks. Finish with `python deploy/verify_live.py https://actcalc.com` and a logged-out visitor test.

**Do not disconnect or point actcalc.com anywhere until the new service and contact backend are verified.** Changing the domain does not automatically transfer browser-saved work; keeping the same exact origin normally preserves it, but advise users to export a backup before launch.

## Local tests

```bash
python -m pip install -r dev-requirements.txt
python build_frontend.py
python -m pytest -q tests/test_backend.py tests/test_backup.py tests/test_release_ops.py tests/test_github_release.py
python deploy/check_inline_scripts.py
python -m playwright install chromium
python tests/qa_browser.py
```

Render routes traffic to the port set by its `PORT` variable (default `10000`); local Compose continues at `localhost:8000`. Do not enable local-dev access on a public server.

See `README_RELEASE.md` for the full operations and deployment gates. `ACTCALC_PUBLIC=false` and all verification flags `false` are intentional. **Do not set them to `true` to bypass missing tests.**
