# Security and data handling

## Implemented controls

- Passwords are stored with Werkzeug's scrypt password hashing.
- Session cookies are HTTP-only, SameSite=Lax, expire after 12 hours, and are marked Secure in production.
- Authenticated state-changing requests require the session CSRF token in `X-CSRF-Token`.
- APIs scope artwork, analytics, and audit queries to the authenticated user's workspace membership.
- Upload size and allowed content are checked server-side. Image data is decoded and format-verified with Pillow; PDFs are checked for their file signature. Filenames are sanitized and never used as object keys.
- Artwork content is encrypted using AES-256-GCM before storage. Nonces are unique per encryption; ciphertext and plaintext hashes are checked on download.
- Image previews are generated in memory from a workspace-authorized, decrypted image, returned as private non-cacheable WebP, and are not written as plaintext thumbnail objects.
- Rate limits apply to registration and login. Security headers are set on responses.

## Boundaries and remaining work

The audit trail is database-backed and is not tamper-proof against a database administrator. There is no external append-only log sink. The starter does not include email verification, password reset, share links, membership/role administration, session revocation, malware scanning, or a managed KMS key-rotation workflow. Production deployments should use TLS, managed secret storage, private S3, least-privilege IAM, durable backups, a shared rate-limit store, dependency updates, and independent security review.

The development encryption key is derived from the development Flask secret when no explicit key is provided. Production refuses to start without explicit secret and encryption keys. Key rotation requires a migration strategy for existing ciphertext and is not automated.

SHA-256 verification answers whether two byte streams match; it is not an ownership or authorship determination.
