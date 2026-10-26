# CAT II rubric evidence checklist

The rubric assigns 8 marks to each of five components (40 total). This checklist maps each one to repository evidence and the live proof still required.

| Rubric component | Project evidence | Demonstration evidence required |
|---|---|---|
| Application development and deployment using public PaaS | React/Flask app, root `Dockerfile`, `render.yaml`, health route, migrations | Deploy the Render blueprint, then record the public HTTPS URL, health response, and working UI. |
| Amazon EC2 instance creation, application deployment, and access | Optional AWS template: `infra/aws/ec2.yaml`, Nginx and systemd examples in `infra/aws/ec2/` | The chosen $0-first setup does not use EC2; this rubric component will not be demonstrated unless an AWS EC2 instance is provisioned. |
| Amazon S3 bucket creation and management | Optional AWS template: `infra/aws/s3-bucket.yaml`. The chosen provider is Cloudflare R2 (S3-compatible), not Amazon S3. | R2 demonstrates S3-compatible object storage, but does not meet a requirement for an Amazon S3 bucket. Use AWS S3 if the assessor requires Amazon. |
| Secure file upload to S3 — confidentiality and integrity | AES-GCM encryption before storage, S3-compatible API, SHA-256 verification, workspace-scoped endpoints | Configure R2 or AWS S3, upload a file, inspect encrypted stored bytes, download the original, and demonstrate a modified-file mismatch. |
| Project documentation, presentation, and viva | `README.md`, `docs/DEPLOYMENT.md`, `docs/MANUAL_TESTING.md`, `docs/SECURITY.md`, and `docs/PRESENTATION.md` | Add actual deployment outputs/screenshots and present the tested workflow; do not claim cloud resources were created unless they were. |

## Completion status

The repository contains deployment templates, application implementation, tests, and presentation material. The current zero-cost-first deployment target is Render Free + Cloudflare R2 and excludes EC2. Render Free Postgres currently expires after 30 days. Creating provider resources requires the student's own accounts and must be verified in their dashboards.
