# Deployment guide

This repository contains a single-origin production container, a Render blueprint, and AWS CloudFormation templates. Cloud resources are not created automatically. Provisioning can incur charges; review the selected plans and AWS estimate before creating stacks.

## Public PaaS: Render

1. Push the project to a Git repository you control and connect that repository in Render.
2. In Render, select **New > Blueprint** and choose the repository. Render reads `render.yaml`, creates the web service and PostgreSQL database, builds the frontend and backend from `Dockerfile`, and applies migrations before deploy.
3. Set the following service variables in Render's dashboard:
   - `ARTLOCK_ENCRYPTION_KEY`: generate locally with `python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"`.
   - `S3_BUCKET`: the private bucket created in the AWS section below.
   - `AWS_REGION`: the bucket's AWS region.
   - `RATELIMIT_STORAGE_URI`: a managed Redis URL for shared production rate limiting.
   - AWS credentials using the PaaS provider's supported identity integration, or a dedicated, restricted IAM identity stored only in the PaaS secret settings. Never commit credentials.
4. Confirm the Render web service is healthy at `/api/v1/health`. Open the service URL, create an account, upload an image, verify it, and download it.
5. Render's generated `ARTLOCK_SECRET_KEY` and managed PostgreSQL URL are used by the service. Keep the encryption key backed up securely; losing it makes stored artwork unreadable.

The Render blueprint uses paid service/database plans so persistent production data is not placed on an ephemeral free database. Review current pricing in the Render dashboard before deployment.

## Amazon S3: create and manage a private bucket

The bucket template enables Block Public Access, bucket-owner-enforced ownership, versioning, default S3-managed encryption, and a bucket policy that denies non-TLS requests.

```powershell
aws cloudformation deploy `
  --template-file infra\aws\s3-bucket.yaml `
  --stack-name artlock-storage `
  --capabilities CAPABILITY_IAM `
  --parameter-overrides BucketName=YOUR-GLOBALLY-UNIQUE-BUCKET-NAME
```

Use a bucket name you control and the AWS region where you plan to run the application. Keep the bucket private. The stack also outputs an IAM managed-policy ARN limited to `GetObject`, `PutObject`, and `DeleteObject` on objects in that bucket. Attach it to a dedicated PaaS identity; the application does not need public access or a bucket listing permission. The EC2 template attaches an equivalent instance role automatically.

For Render, use a distinct IAM identity with only the same object actions on `arn:aws:s3:::YOUR-BUCKET/*`. Add no console login, public permissions, or access to unrelated buckets. Save its credentials only in the Render dashboard, rotate them if exposed, and use an account-supported short-lived identity integration where available.

Verify the bucket settings in the AWS console and inspect object versions after a test upload. Versioning can increase storage costs; configure a reviewed lifecycle/retention policy if needed.

## Amazon EC2: create the host, deploy ArtLock, and access it

### 1. Prepare AWS prerequisites

- Create or select a VPC and a **public subnet** with a route to an internet gateway. Note the VPC and subnet IDs.
- Create an EC2 key pair and retain its private key securely.
- Determine your current public IPv4 address; pass it as `x.x.x.x/32` for restricted SSH access.
- Create the S3 bucket first using the previous section, in the same AWS region.

### 2. Create the EC2 stack

```powershell
aws cloudformation deploy `
  --template-file infra\aws\ec2.yaml `
  --stack-name artlock-ec2 `
  --capabilities CAPABILITY_IAM `
  --parameter-overrides `
    BucketName=YOUR-BUCKET `
    VpcId=vpc-0123456789abcdef0 `
    SubnetId=subnet-0123456789abcdef0 `
    KeyName=YOUR-KEY-PAIR `
    SshCidr=YOUR.PUBLIC.IP.ADDRESS/32
```

The template creates an Ubuntu EC2 instance with encrypted EBS, IMDSv2 required, an instance profile scoped to the selected bucket, SSH restricted to your CIDR, and HTTP/HTTPS ingress. It installs Python virtual-environment tooling and Nginx. Retrieve its public IP:

```powershell
aws cloudformation describe-stacks `
  --stack-name artlock-ec2 `
  --query "Stacks[0].Outputs"
```

### 3. Build and copy the application

Build the frontend from the project root so Flask can serve it from `frontend\dist`:

```powershell
npm --prefix frontend ci
npm --prefix frontend run build
ssh -i C:\path\to\your-key.pem ubuntu@EC2_PUBLIC_IP "mkdir -p /tmp/artlock/frontend"
scp -i C:\path\to\your-key.pem -r backend migrations ubuntu@EC2_PUBLIC_IP:/tmp/artlock/
scp -i C:\path\to\your-key.pem -r frontend\dist ubuntu@EC2_PUBLIC_IP:/tmp/artlock/frontend/
scp -i C:\path\to\your-key.pem infra\aws\ec2\artlock.service infra\aws\ec2\nginx.conf ubuntu@EC2_PUBLIC_IP:/tmp/
```

On the instance, install and configure the app (replace `EC2_PUBLIC_IP` only for the SSH command):

```bash
sudo mkdir -p /opt/artlock /var/lib/artlock /etc/artlock
sudo cp -R /tmp/artlock/backend /tmp/artlock/migrations /opt/artlock/
sudo mkdir -p /opt/artlock/frontend
sudo cp -R /tmp/artlock/frontend/dist /opt/artlock/frontend/
sudo python3 -m venv /opt/artlock/.venv
sudo /opt/artlock/.venv/bin/pip install -r /opt/artlock/backend/requirements.txt
sudo chown -R root:www-data /opt/artlock
sudo chmod -R o-w /opt/artlock
sudo chown -R www-data:www-data /var/lib/artlock
sudo chmod 0750 /var/lib/artlock
sudo install -m 0644 /tmp/artlock.service /etc/systemd/system/artlock.service
sudo install -m 0644 /tmp/nginx.conf /etc/nginx/sites-available/artlock
sudo ln -sf /etc/nginx/sites-available/artlock /etc/nginx/sites-enabled/artlock
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl reload nginx
```

Create `/etc/artlock/artlock.env` as root with mode `0600`; provide real generated secrets and your bucket name/region. Do not paste secrets into shell history or commit them:

```dotenv
ARTLOCK_ENV=production
ARTLOCK_SECRET_KEY=replace-with-a-random-secret-at-least-32-characters
ARTLOCK_ENCRYPTION_KEY=replace-with-a-url-safe-base64-encoded-32-byte-key
DATABASE_URL=sqlite:////var/lib/artlock/artlock.db
STORAGE_BACKEND=s3
S3_BUCKET=YOUR-BUCKET
AWS_REGION=YOUR-AWS-REGION
RATELIMIT_STORAGE_URI=memory://
```

The systemd unit reads the environment file, applies pending migrations as `www-data` before startup, then starts Gunicorn. Enable the service:

```bash
sudo chown root:root /etc/artlock/artlock.env
sudo chmod 0600 /etc/artlock/artlock.env
sudo systemctl daemon-reload
sudo systemctl enable --now artlock
```

Open `http://EC2_PUBLIC_IP/` and confirm `http://EC2_PUBLIC_IP/api/v1/health`. HTTP is for initial demonstration only. Before production, associate a domain, configure TLS certificates at Nginx or a load balancer, and redirect/allow only HTTPS. Do not open Gunicorn's port 5000 to the internet. Use Systems Manager instead of SSH where configured.

The supplied EC2 example uses a single-host SQLite database for a straightforward demonstration. For production, use managed PostgreSQL, durable backups, a shared rate-limit store, monitoring, and a tested recovery plan.

## Secure upload and integrity demonstration

1. Sign in and upload an allowed image or PDF.
2. ArtLock calculates SHA-256 over the original bytes and encrypts them with AES-256-GCM before object storage.
3. S3 also applies its configured server-side encryption. The application records a ciphertext checksum and verifies ciphertext and plaintext hashes on download.
4. Download the file and confirm the bytes match the original; submit a modified file and demonstrate `MISMATCH`.
5. Confirm an unauthenticated user cannot access the artwork and that no S3 object is publicly accessible.

SHA-256 equality proves byte equality only; it does not establish authorship, originality, or legal ownership.

## Release checklist

- Apply/review database migrations before deploying new code.
- Verify TLS, `/api/v1/health`, registration/login, workspace isolation, upload, download, and modified-file mismatch.
- Confirm bucket public access blocks, IAM scope, encrypted backups, key custody, and retention settings.
- Keep `ARTLOCK_SECRET_KEY` and `ARTLOCK_ENCRYPTION_KEY` out of source control. A lost encryption key cannot be reconstructed from stored objects.
- Capture actual provider/AWS console and terminal evidence for the CAT II presentation. The templates are reproducible setup aids, not evidence that cloud deployment has already occurred.
