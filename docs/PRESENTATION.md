# ArtLock CAT II presentation and viva

Use this as a slide-by-slide presentation outline. Replace deployment placeholders with screenshots and outputs from your own provider accounts; do not present unperformed cloud steps as completed work. The selected $0-first architecture uses Render + Cloudflare R2 and does not meet rubric requirements that specifically demand EC2 or Amazon S3.

## Slide 1 — Project and rubric map (8 marks)

- ArtLock: secure artwork registration and integrity verification.
- Show the five rubric components and where each is evidenced in the project.
- Demonstration setup: Render Free hosts the application; Cloudflare R2 stores encrypted objects using its S3-compatible API.

## Slide 2 — Application design and public PaaS (8 marks)

- React/TypeScript single-page dashboard served by Flask, SQLAlchemy data, and PostgreSQL in production.
- Render deployment uses `render.yaml` and the root `Dockerfile`; migrations run before startup and `/api/v1/health` is the health check.
- Demonstrate the live HTTPS URL, health endpoint, registration, and dashboard after your deployment succeeds.
- Explain managed secrets and persistent database/object-storage configuration.

## Slide 3 — Hosting alternative: Render (EC2 rubric item not met)

- Explain why the project uses Render Free instead of EC2 under the $0 spend constraint.
- Show the Render service, deployment, sleep behavior, and health check.
- State clearly that this does not earn the EC2 instance creation/deployment/access marks.

## Slide 4 — Cloudflare R2 storage (AWS S3 rubric item not met)

- Demonstrate the private R2 bucket and scoped API token without revealing credentials.
- Explain the R2 free allowance and billing/usage monitoring.
- State clearly that R2 is S3-compatible but is not Amazon S3 and does not earn Amazon-S3-specific bucket marks.

## Slide 5 — Secure file upload, confidentiality, and integrity (8 marks)

- Upload an artwork through the authenticated vault.
- Explain SHA-256 of original bytes and AES-256-GCM encryption before storage; R2 handles provider-side encryption at rest.
- Download and verify the original; change the file and show a mismatch.
- Explain workspace authorization and that matching hashes prove byte equality, not authorship or ownership.

## Slide 6 — Documentation, test evidence, and viva (8 marks)

- Show README setup, deployment guide, manual test checklist, architecture notes, and this presentation outline.
- Run the backend test suite and frontend production build; include the actual terminal output in your final slides.
- Discuss operational limitations: Render Free sleeps and its free Postgres expires after 30 days; R2 is not Amazon S3; retain and back up encryption keys.

## Viva questions to prepare for

1. Why encrypt application bytes before storing them in S3 if S3 also encrypts the bucket?
2. What does SHA-256 equality establish, and what does it not establish?
3. Why keep the object bucket private and restrict API tokens to a single bucket?
4. How does the S3-compatible API let one application work with multiple object-storage providers?
5. What happens to an upload if storage succeeds but the database transaction fails?
6. Which production secrets must be backed up, and what is the impact of losing the encryption key?
7. How do you validate the health endpoint, migration status, and upload/download workflow after deployment?
