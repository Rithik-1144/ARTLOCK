import { useState } from 'react'
import { Download, FileSearch, LoaderCircle, ShieldAlert, ShieldCheck, Upload } from 'lucide-react'

type ForensicArtwork = {
  id: string
  title: string
  filename: string
  content_type: string
}

export type Comparison = {
  id: string
  artwork_id: string
  artwork_title: string
  artwork_filename: string
  artwork_content_type: string
  artwork_sha256: string
  candidate_filename: string
  candidate_content_type: string
  candidate_file_size: number
  candidate_sha256: string
  artwork_width: number | null
  artwork_height: number | null
  candidate_width: number | null
  candidate_height: number | null
  exact_match: boolean
  similarity_percent: number | null
  similarity_method: string | null
  created_at: string
  preview_url: string
  artwork_preview_url: string | null
  report_url: string
}

export function ForensicsLab({
  artworks,
  csrfToken,
  comparisons,
  loadingHistory,
  historyError,
  onRefresh,
  onCreated,
}: {
  artworks: ForensicArtwork[]
  csrfToken: string
  comparisons: Comparison[]
  loadingHistory: boolean
  historyError: string
  onRefresh: () => void
  onCreated: (comparison: Comparison) => void
}) {
  const [artworkId, setArtworkId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const compare = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!artworkId || !file) {
      setError('Choose registered artwork and a candidate file.')
      return
    }
    setBusy(true)
    setError('')
    const body = new FormData()
    body.set('artwork_id', artworkId)
    body.set('file', file)
    try {
      const response = await fetch('/api/v1/forensics/comparisons', {
        method: 'POST',
        credentials: 'include',
        headers: { 'X-CSRF-Token': csrfToken },
        body,
      })
      const result = (await response.json()) as { comparison?: Comparison; error?: string }
      if (!response.ok) throw new Error(result.error ?? `Request failed (${response.status})`)
      const comparison = result.comparison
      if (!comparison) throw new Error('The server returned no comparison record.')
      onCreated(comparison)
      setFile(null)
      const input = document.querySelector<HTMLInputElement>('#forensics-candidate')
      if (input) input.value = ''
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Comparison could not be completed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="page-heading">
        <span className="eyebrow">ARTWORK FORENSICS</span>
        <h1>Forensics Lab</h1>
        <p>Compare a candidate with registered artwork and keep a private, encrypted comparison record.</p>
      </div>
      <section className="panel forensics-form-panel">
        <div className="panel-heading">
          <div><h2>New comparison</h2><p>Exact file identity and visual similarity are reported separately.</p></div>
          <FileSearch size={18} className="subtle-icon" />
        </div>
        {artworks.length ? (
          <form className="forensics-form" onSubmit={(event) => void compare(event)}>
            <label className="field-label">Registered artwork
              <select required value={artworkId} onChange={(event) => setArtworkId(event.target.value)}>
                <option value="">Choose artwork…</option>
                {artworks.map((artwork) => (
                  <option value={artwork.id} key={artwork.id}>{artwork.title} · {artwork.filename}</option>
                ))}
              </select>
            </label>
            <label className="dropzone forensics-dropzone">
              <input
                id="forensics-candidate"
                type="file"
                accept=".png,.jpg,.jpeg,.webp,.pdf"
                required
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
              <span className="drop-icon"><Upload size={18} /></span>
              <strong>{file?.name ?? 'Choose a candidate file'}</strong>
              <small>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB · Encrypted on upload` : 'PNG, JPEG, WebP, or PDF · Up to 25 MB'}</small>
            </label>
            <button className="button button-primary" disabled={busy || !file || !artworkId}>
              {busy ? <LoaderCircle className="spin" size={15} /> : <FileSearch size={15} />}
              {busy ? 'Analyzing securely…' : 'Compare artwork'}
            </button>
          </form>
        ) : (
          <div className="inline-empty"><FileSearch size={18} /><span>Register artwork before starting a comparison.</span></div>
        )}
        <div className="forensics-disclaimer">
          <ShieldCheck size={15} />
          <span>SHA-256 confirms byte equality only. The 64-bit dHash similarity is a screening estimate, not proof of authorship, copying, or ownership. PDFs are compared by SHA-256 only.</span>
        </div>
        {error && <div className="form-error" role="alert"><ShieldAlert size={16} />{error}</div>}
      </section>

      <section className="panel forensics-history">
        <div className="panel-heading">
          <div><h2>Comparison history</h2><p>{comparisons.length} recent workspace records · up to 100 shown</p></div>
          <button className="text-button" onClick={onRefresh} disabled={loadingHistory}>Refresh</button>
        </div>
        {historyError && <div className="form-error" role="alert"><ShieldAlert size={16} />{historyError}</div>}
        {loadingHistory ? <div className="inline-empty"><LoaderCircle className="spin" size={18} /><span>Loading comparison history…</span></div>
          : comparisons.length ? <div className="forensics-comparison-list">
            {comparisons.map((comparison) => <ComparisonCard key={comparison.id} comparison={comparison} />)}
          </div>
            : <div className="inline-empty"><FileSearch size={18} /><span>No comparisons have been recorded yet.</span></div>}
      </section>
    </>
  )
}

function ComparisonCard({ comparison }: { comparison: Comparison }) {
  return (
    <article className="forensics-record">
      <div className="forensics-record-heading">
        <div>
          <strong>{comparison.artwork_title}</strong>
          <span>{new Date(comparison.created_at).toLocaleString()} · Candidate: {comparison.candidate_filename}</span>
        </div>
        <a className="button button-secondary compact-button" href={comparison.report_url}>
          <Download size={13} />Report
        </a>
      </div>
      <div className="forensics-results">
        <div className={`forensics-result ${comparison.exact_match ? 'result-match' : 'result-different'}`}>
          <span>EXACT SHA-256</span><strong>{comparison.exact_match ? 'MATCH' : 'NO MATCH'}</strong>
        </div>
        <div className="forensics-result">
          <span>VISUAL SIMILARITY</span>
          <strong>{comparison.similarity_percent === null ? 'Not available' : `${comparison.similarity_percent}%`}</strong>
          {comparison.similarity_method && <small>{comparison.similarity_method}</small>}
        </div>
        <div className="forensics-result">
          <span>IMAGE DIMENSIONS</span>
          <strong>{comparison.candidate_width && comparison.candidate_height
            ? `${comparison.candidate_width} × ${comparison.candidate_height}`
            : 'Not available'}</strong>
        </div>
      </div>
      {comparison.artwork_preview_url && comparison.candidate_content_type.startsWith('image/') && (
        <div className="forensics-previews">
          <figure><img src={comparison.artwork_preview_url} alt={`Registered ${comparison.artwork_title}`} /><figcaption>Registered artwork · {comparison.artwork_filename}</figcaption></figure>
          <figure><img src={comparison.preview_url} alt={`Candidate ${comparison.candidate_filename}`} /><figcaption>Candidate · {comparison.candidate_filename}</figcaption></figure>
        </div>
      )}
      <div className="forensics-hashes">
        <span>REGISTERED <code>{comparison.artwork_sha256}</code></span>
        <span>CANDIDATE <code>{comparison.candidate_sha256}</code></span>
      </div>
    </article>
  )
}
