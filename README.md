# ArtLock

ArtLock is a secure artwork registration and integrity-vault application. The implemented core includes a responsive React/TypeScript dashboard, Flask API, persistent SQLAlchemy data, cookie-based authentication, workspace isolation, AES-256-GCM encrypted object storage, SHA-256 registration and comparison, immutable version history records, archive/restore, favorites, editable categories and tags, search/filter/sort, secured inventory CSV export, audit events, and live database-backed analytics.

> **Current scope:** this is a working application core, not the full enterprise feature list. PDF certificates, sharing, collections, collaboration, watermarking, in-app notifications, account recovery, email verification, member administration, quotas, and pixel-level image comparison are not implemented. Inventory CSV export is implemented.

## Requirements

- Python 3.11+
- Node.js 20.19+ or 22.12+ (Vite 8 requirement)
- npm

## Local setup (Windows PowerShell)

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
npm --prefix frontend install
```

Replace both `ARTLOCK_SECRET_KEY` and `ARTLOCK_ENCRYPTION_KEY` in `.env` with randomly generated values. For the encryption key:

```powershell
python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

Keep `.env`, the encryption key, and database/object-storage backups private. The default local configuration stores encrypted objects in `backend/instance/objects` and SQLite metadata in `backend/instance/artlock.db`. Local-development defaults are not production secrets.

### Database

The Flask-Migrate extension and initial migration are included. Apply it to the configured database:

```powershell
$env:FLASK_APP = "backend/run.py"
python -m flask db upgrade
```

After a model change, generate a migration with `python -m flask db migrate -m "Describe schema change"` and review it before applying with `python -m flask db upgrade`.

Run migrations for each schema update. The production Docker entrypoint applies pending migrations before starting Gunicorn; non-Docker deployments must run `flask --app backend/run.py db upgrade` as a release/start step. Tests create isolated temporary databases.

### Start the services

In one PowerShell terminal:

```powershell
$env:FLASK_APP = "backend/run.py"
python -m flask run --host 127.0.0.1 --port 5000
```

In another:

```powershell
npm --prefix frontend run dev
```

Vite forwards `/api` requests to the Flask server. Open the URL Vite prints, register an account, and upload a PNG, JPEG, WebP, or PDF up to the configured limit (25 MiB by default). The dashboard refreshes workspace metrics every 30 seconds while visible and after key operations.

### Load the demonstration gallery

Sign in to your workspace and click **Load sample gallery** on the empty dashboard. The authenticated, repeatable action adds the ten generated demonstration artworks to the current workspace, records real verification comparisons, and skips samples already loaded. This also works on the deployed Render app.

For a local workspace, the seeder CLI is also available:

```powershell
python backend\seed_demo.py --email your-account@example.com
```

The seeder writes the sample PNGs to `backend/demo_assets`, then registers them through the normal authenticated API upload path. Artwork is encrypted and hashed; six originals are compared to create match records, and a pixel-altered copy creates a mismatch example. Existing demo entries and the mismatch example are skipped on reruns; other artwork is not deleted or overwritten. The samples are marked as generated demonstrations, not user-created originals. The CLI requires an existing account and does not create a default password or demo login.

## Verification & encryption model

- The SHA-256 digest identifies the original, plaintext bytes. Comparisons hash the submitted bytes on the backend and compare the actual digest.
- Objects are encrypted before local or S3 storage using AES-256-GCM, with a unique random 96-bit nonce per encryption and the authentication tag included in the ciphertext. Ciphertext is independently checksummed.
- Downloads are authorized by workspace membership, then ciphertext and plaintext checksums are verified, and authenticated decryption happens server-side.
- Local mode is encrypted storage on the configured local disk, not a cloud service. Production should use a private S3 bucket, restricted IAM role, HTTPS, managed secrets, durable PostgreSQL, and a shared rate-limit store.
- SHA-256 equality confirms byte equality only. It does not prove ownership, authorship, originality, or legal rights.

## Free-first Render and S3-compatible storage

The selected deployment is Render Free for the app and Cloudflare R2 for S3-compatible object storage; no EC2 instance is required. The root `Dockerfile` builds and serves the frontend and Flask app as one service. `render.yaml` describes the Free web service and database. See [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) for account setup, environment variables, and verification.

Configure `STORAGE_BACKEND=s3`, `S3_BUCKET`, `AWS_REGION=auto`, `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, and `S3_SECRET_ACCESS_KEY` in Render. R2 is S3-compatible but is not Amazon S3, so this deployment does not satisfy an AWS-S3-specific rubric requirement. The AWS S3 and EC2 CloudFormation files remain optional alternatives and can incur charges.

Render Free's local filesystem is ephemeral, its web service sleeps when idle, and its free PostgreSQL database currently expires after 30 days. R2's free allowances are limited and usage beyond them can incur charges. Verify provider billing terms and usage before deployment.

## Tests and frontend checks

```powershell
python -m pytest backend\tests -q
npm --prefix frontend run build
npm --prefix frontend run lint
```

Tests cover registration/login, CSRF enforcement, workspace isolation, file validation, duplicate detection, encrypted object retrieval, SHA-256 matches/mismatches, version preservation, and AES-GCM authentication failure.

## Production and hosting notes

For production, use PostgreSQL and apply migrations during release. Set `ARTLOCK_ENV=production`, a strong `ARTLOCK_SECRET_KEY`, and a URL-safe base64 `ARTLOCK_ENCRYPTION_KEY` that decodes to exactly 32 bytes. Do not rely on Flask's development server, local ephemeral disk, the in-memory rate limiter, or local SQLite for a multi-instance deployment. Configure HTTPS termination, persistent encrypted backups, a shared rate-limit backend, log retention, and monitoring.

Deployment templates are starting points, not proof of completed provisioning. Actual Render and R2 account setup remains account-dependent and must be verified in the provider dashboards.

## Important limitations

- The starter app provisions a private workspace per account; it does not yet support member invitations, role editing, or workspace switching.
- Versions are preserved with per-version hashes and metadata, but there is not yet a restore-current-version endpoint.
- Signup does not include email verification or password reset.
- Login throttling uses Flask-Limiter's configured backend. Use Redis or another shared persistent backend in production.
- PDF certificates, watermarks, sharing links, comments, collection CRUD, notifications, report/PDF exports, quota enforcement, and admin controls remain future work.
- Image previews are generated from the authorized, decrypted original on request and are not stored as unencrypted thumbnails. PDFs are represented as documents rather than fabricated artwork previews.
