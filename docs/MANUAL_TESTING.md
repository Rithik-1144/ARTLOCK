# Manual test checklist and CAT II demonstration

## Functional checks

1. Start Flask and Vite using the README instructions and confirm `/api/v1/health` reports `status: ok` and the configured backend.
2. Register a new account, workspace, and 12-character-minimum password. Sign out and sign back in.
3. On an empty authenticated dashboard, select **Load sample gallery**. Confirm ten generated demonstration artworks appear in the vault. Repeat the action and confirm it does not create duplicates. Confirm six matches and one modified-file mismatch are recorded.
4. Open the dashboard and confirm its artwork count, verification totals, favorite count, storage usage, trends, file-type visualization, category mix, and activity reflect workspace database data.
5. Open a sample artwork, inspect its generated authorized preview and registered SHA-256, then download the artwork. Confirm the downloaded bytes match the local sample PNG.
6. In **Verification**, submit the original sample file and confirm `MATCH` and identical SHA-256 values. Change one pixel or byte and confirm `MISMATCH`.
7. In **Forensics Lab**, compare an image with itself and confirm exact SHA-256 match, 100% dHash similarity, image previews, and a downloadable JSON report. Compare a different image and confirm exact match is shown separately from the dHash estimate. Compare a PDF and confirm visual similarity is unavailable.
8. Try a duplicate upload, invalid file bytes with an image extension, and a file over the configured size limit; confirm each is rejected with a useful message.
9. Add a new version with notes. Confirm the timeline contains both versions and their distinct hashes.
10. Change artwork title, description, category, and tags in its detail panel. Save and verify the new values persist; search by a tag.
11. Favorite/unfavorite an artwork, use the favorites and file-type filters, and sort by name, date, and size.
12. Download the inventory CSV and confirm it contains only the current workspace's actual authorized records.
13. Archive and restore artwork. Confirm it moves between the active and archived vault filters.
14. Register a second account and confirm it cannot view, preview, download, compare, or export the first account's artwork or forensic history.
15. Inspect Activity & audit and the dashboard to confirm registration, download, version, favorite, metadata, export, verification, and forensics operations were persisted.
16. Inspect local object storage: registered and forensic candidate object bytes should not be readable as the original image/PDF. Use authorized previews/downloads to verify decryption works.
17. Resize the browser to a mobile viewport, use the mobile menu, and verify the dashboard, vault, dialogs, and forms remain usable.

## CAT II viva demonstration outline

1. Explain the problem: keeping durable file metadata and checking whether a candidate file is byte-identical to a registered reference.
2. Show the workspace authentication and database-backed artwork list.
3. Upload a sample image. Explain server-side content validation, SHA-256 of original plaintext, AES-256-GCM encryption, nonce storage, and ciphertext checksum.
4. Demonstrate matching and modified-file mismatch results. Clarify that a hash match confirms byte equality, not authorship or copyright.
5. Add a version and show immutable per-version hash history.
6. Show workspace-scoped API access, CSRF handling, audit rows, and the migration-managed schema.
7. Explain local encrypted disk versus configured private S3. Do not claim AWS has been used unless an actual S3 account is configured and an integration test has succeeded.
8. Discuss limitations honestly: member collaboration, sharing, certificates, watermarks, and other unimplemented modules are not part of the current working core.
