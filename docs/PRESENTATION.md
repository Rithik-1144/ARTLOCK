# ArtLock CAT II presentation and viva

Use this as a slide-by-slide presentation outline. Replace the deployment placeholders with screenshots and outputs from your own AWS/PaaS accounts; do not present unperformed cloud steps as completed work.

## Slide 1 — Project and rubric map (8 marks)

- ArtLock: secure artwork registration and integrity verification.
- Show the five rubric components and where each is evidenced in the project.
- Demonstration setup: local development is available; public deployment requires your configured Render and AWS accounts.

## Slide 2 — Application design and public PaaS (8 marks)

- React/TypeScript single-page dashboard served by Flask, SQLAlchemy data, and PostgreSQL in production.
- Render deployment uses `render.yaml` and the root `Dockerfile`; migrations run before deploy and `/api/v1/health` is the health check.
- Demonstrate the live HTTPS URL, health endpoint, registration, and dashboard after your deployment succeeds.
- Explain managed secrets and persistent database/object-storage configuration.

## Slide 3 — Amazon EC2 instance and application access (8 marks)

- Show the EC2 CloudFormation stack, instance state, instance profile, encrypted EBS volume, and security group.
- SSH is limited to an administrator `/32`; browser traffic uses ports 80/443.
- Deploy the project behind Nginx and Gunicorn with the supplied systemd/Nginx examples.
- Show the public application URL and health check. Add TLS using a domain and certificate before production use.

## Slide 4 — S3 bucket creation and management (8 marks)

- Create the bucket with `infra/aws/s3-bucket.yaml`.
- Demonstrate Block Public Access, bucket-owner-enforced ownership, default SSE-S3 encryption, versioning, and TLS-only bucket policy.
- Explain IAM role-based EC2 access and the least-privilege object actions; do not publish bucket credentials.
- Show bucket versions and application-generated object keys in the AWS console.

## Slide 5 — Secure file upload, confidentiality, and integrity (8 marks)

- Upload an artwork through the authenticated vault.
- Explain SHA-256 of original bytes, AES-256-GCM application encryption before storage, and S3 server-side encryption.
- Download and verify the original; change the file and show a mismatch.
- Explain workspace authorization and that matching hashes prove byte equality, not authorship or ownership.

## Slide 6 — Documentation, test evidence, and viva (8 marks)

- Show README setup, deployment guide, manual test checklist, architecture notes, and this presentation outline.
- Run the backend test suite and frontend production build; include the actual terminal output in your final slides.
- Discuss operational limitations: AWS account-specific deployment remains the operator's responsibility; retain and back up encryption keys; configure domain TLS and shared rate limiting.

## Viva questions to prepare for

1. Why encrypt application bytes before storing them in S3 if S3 also encrypts the bucket?
2. What does SHA-256 equality establish, and what does it not establish?
3. Why are S3 public access blocked and EC2 SSH restricted?
4. How does the EC2 instance access S3 without embedding AWS access keys?
5. What happens to an upload if storage succeeds but the database transaction fails?
6. Which production secrets must be backed up, and what is the impact of losing the encryption key?
7. How do you validate the health endpoint, migration status, and upload/download workflow after deployment?
