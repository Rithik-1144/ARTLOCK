# Deployment guide: free-first Render + Cloudflare R2

The selected setup uses Render for the web application and Cloudflare R2 for S3-compatible encrypted object storage. It does not deploy to EC2. R2 is **not Amazon S3**; use the AWS template in `infra/aws/s3-bucket.yaml` instead if the rubric strictly requires AWS S3.

Free plans have limits and can change. Check current provider billing before adding payment methods or enabling paid resources.

## 1. Set up Cloudflare R2

1. Create or sign in to a Cloudflare account and open **R2 Object Storage**.
2. Create a private bucket using the Standard storage class. Do not enable public bucket access.
3. In R2 API tokens, create a token scoped only to this bucket with object read/write permission. Copy its access key and secret once; store them in a password manager.
4. From the Cloudflare account's R2 overview, copy the account ID. The S3-compatible endpoint is:

   ```text
   https://ACCOUNT_ID.r2.cloudflarestorage.com
   ```

5. Do not enable public access, publish the token, or add it to the Git repository. R2 applies provider-managed encryption at rest; ArtLock also encrypts content with AES-256-GCM before upload.

Cloudflare's documented R2 free tier currently includes up to 10 GB-month of Standard storage, 1 million Class A requests, 10 million Class B requests, and free egress each month. Usage above those allowances can be billed; configure provider alerts and monitor usage.

## 2. Configure Render

The root `render.yaml` uses a Free web service and a Free Render Postgres instance. Render Free web services sleep after inactivity and have ephemeral filesystems, so local SQLite and local uploaded objects are not durable. Render Free Postgres currently expires 30 days after creation; after its grace period, its data is deleted. This is suitable only for a short-lived demonstration unless you export/backup data and migrate to another persistent database.

1. Push the project to a Git repository and connect it to Render.
2. In Render, create a Blueprint from this repository. Review all resources and ensure the service/database plan is **Free** before confirming.
3. Configure the following web-service environment variables in the Render dashboard. Blueprint `sync: false` secrets on an already-existing service must be entered manually:

   | Variable | Value |
   |---|---|
   | `ARTLOCK_ENV` | `production` |
   | `ARTLOCK_SECRET_KEY` | Generate a unique random secret (Render may generate this automatically). |
   | `ARTLOCK_ENCRYPTION_KEY` | Generate locally with the command below; back it up securely. Losing it makes uploaded art unreadable. |
   | `DATABASE_URL` | Render Postgres connection string, preferably the Internal URL when available. |
   | `STORAGE_BACKEND` | `s3` |
   | `S3_BUCKET` | Your R2 bucket name. |
   | `AWS_REGION` | `auto` |
   | `S3_ENDPOINT_URL` | `https://ACCOUNT_ID.r2.cloudflarestorage.com` |
   | `S3_ACCESS_KEY_ID` | R2 token access key. Mark secret. |
   | `S3_SECRET_ACCESS_KEY` | R2 token secret. Mark secret. |
   | `RATELIMIT_STORAGE_URI` | `memory://` for this single-instance demo only. |

   Generate the 32-byte URL-safe base64 encryption key locally:

   ```powershell
   python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
   ```

4. Deploy. The production Docker startup runs database migrations before Gunicorn. Check `https://YOUR-SERVICE.onrender.com/api/v1/health`; with R2 correctly configured it should report `"status":"ok"` and `"storage":"s3"`.
5. Register a test account, upload an image, download it, and compare the download's bytes to the original. Verify a modified image produces `MISMATCH`. Confirm the object appears in the private R2 bucket.

### Important: existing Render service

An existing service created manually does not automatically receive all environment variables from Blueprint `sync: false` entries. Set them in **Render → your service → Environment** and redeploy. Switching storage from `local` to R2 does not migrate files previously stored on Render's ephemeral filesystem. Re-upload any demo files you still need.

## 3. Verify the free-first workflow

```powershell
python -m pytest backend\tests -q
npm --prefix frontend run build
```

On Render, verify:

- `/api/v1/health` returns HTTP 200 and `storage: s3`.
- Registration, login/logout, artwork upload, preview, download, and modified-file verification work.
- R2 contains ciphertext objects, not the original PNG/PDF bytes.
- Browser access is HTTPS; credentials are not in Git history or logs.
- Provider usage/billing dashboards remain within the free allowances.

## Alternative: Amazon EC2 and Amazon S3

If the rubric requires AWS specifically, the repository retains `infra/aws/ec2.yaml` and `infra/aws/s3-bucket.yaml` with Nginx/systemd examples under `infra/aws/ec2/`. These are optional and may incur AWS charges. They are not part of the selected zero-cost deployment.

## Security and limits

- The app encrypts file bytes with AES-256-GCM before sending them to object storage and verifies ciphertext and plaintext SHA-256 digests on download.
- Keep Render secrets and R2 API credentials private. Use a bucket-scoped, least-privilege token and rotate it if exposed.
- Do not put secrets in `render.yaml`, `.env.example`, or Git.
- A free plan is not a production availability or durability guarantee. Free compute can sleep, local files are ephemeral, and the free database expires.
- SHA-256 equality proves byte equality only; it does not establish authorship or ownership.
