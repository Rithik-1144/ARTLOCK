# CAT II rubric evidence checklist

The rubric assigns 8 marks to each of five components (40 total). This checklist maps each one to repository evidence and the live proof still required.

| Rubric component | Project evidence | Demonstration evidence required |
|---|---|---|
| Application development and deployment using public PaaS | React/Flask app, root `Dockerfile`, `render.yaml`, health route, migrations | Deploy the Render blueprint, then record the public HTTPS URL, health response, and working UI. |
| Amazon EC2 instance creation, application deployment, and access | `infra/aws/ec2.yaml`, Nginx and systemd examples in `infra/aws/ec2/`, deployment guide | Create the stack in your AWS account, deploy the app, and show instance, security-group, and browser-access screenshots. |
| Amazon S3 bucket creation and management | `infra/aws/s3-bucket.yaml` provisions a private versioned bucket and TLS-only policy | Create the stack and show bucket settings, object versioning, and Block Public Access in the AWS console. |
| Secure file upload to S3 — confidentiality and integrity | AES-GCM encryption before storage, S3 SSE, SHA-256 verification, workspace-scoped endpoints | Configure the bucket, upload a file, inspect encrypted stored bytes, download the original, and demonstrate a modified-file mismatch. |
| Project documentation, presentation, and viva | `README.md`, `docs/DEPLOYMENT.md`, `docs/MANUAL_TESTING.md`, `docs/SECURITY.md`, and `docs/PRESENTATION.md` | Add actual deployment outputs/screenshots and present the tested workflow; do not claim cloud resources were created unless they were. |

## Completion status

The repository contains deployment templates, application implementation, tests, and presentation material. Public PaaS and AWS resources have **not** been created from this workspace; doing so requires the student's account, region, selected network/domain, and explicit approval for billable resources.
