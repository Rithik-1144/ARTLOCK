import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import {
  ArrowDownToLine,
  ArrowRight,
  Bell,
  Check,
  ChevronDown,
  CircleHelp,
  Clock3,
  FileImage,
  FileSearch,
  Fingerprint,
  FolderOpen,
  Gauge,
  ImagePlus,
  LayoutDashboard,
  LoaderCircle,
  LogOut,
  Menu,
  MoreHorizontal,
  Plus,
  Search,
  Settings,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Star,
  Upload,
  X,
} from 'lucide-react'
import './App.css'

const RegistrationChart = lazy(() => import('./RegistrationChart'))
const StorageTrend = lazy(() =>
  import('./AnalyticsCharts').then((module) => ({ default: module.StorageTrend })),
)
const FileTypeDonut = lazy(() =>
  import('./AnalyticsCharts').then((module) => ({ default: module.FileTypeDonut })),
)

type User = { email: string; display_name: string }
type Artwork = {
  id: string
  title: string
  description: string
  filename: string
  content_type: string
  file_size: number
  sha256: string
  version_number: number
  archived: boolean
  created_at: string
  creator: string
  favorite: boolean
  category: string
  tags: string[]
  versions?: Version[]
}
type Version = {
  id: string
  version_number: number
  filename: string
  file_size: number
  sha256: string
  notes: string
  created_at: string
}
type Overview = {
  total_artworks: number
  total_storage_bytes: number
  verified: number
  mismatches: number
  by_type: Record<string, number>
  recent: Artwork[]
  registration_trend: { date: string; registrations: number }[]
  storage_trend: { date: string; storage_bytes: number }[]
  categories: { name: string; count: number }[]
  versions_count: number
  favorite_count: number
  total_verifications: number
  latest_verification: { result: 'MATCH' | 'MISMATCH'; created_at: string } | null
  recent_events: AuditEvent[]
}
type AuditEvent = {
  id: number
  actor: string
  action: string
  target_id: string | null
  outcome: string
  created_at: string
}
type Verification = {
  result: 'MATCH' | 'MISMATCH'
  registered_sha256: string
  calculated_sha256: string
  verified_at: string
}

const navItems = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'vault', label: 'Artwork vault', icon: FolderOpen },
  { id: 'verification', label: 'Verification', icon: Fingerprint },
  { id: 'activity', label: 'Activity & audit', icon: Clock3 },
]

function formatBytes(bytes: number) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(
    new Date(value),
  )
}

async function request<T>(path: string, csrfToken = '', init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (csrfToken) headers.set('X-CSRF-Token', csrfToken)
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers,
    credentials: 'include',
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { error?: string }
    throw new Error(body.error ?? `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

function App() {
  const [todayLabel] = useState(() =>
    new Intl.DateTimeFormat(undefined, { weekday: 'long', month: 'long', day: 'numeric' })
      .format(new Date())
      .toUpperCase(),
  )
  const [user, setUser] = useState<User | null | undefined>(undefined)
  const [workspaceName, setWorkspaceName] = useState('Workspace')
  const [csrfToken, setCsrfToken] = useState('')
  const [view, setView] = useState('overview')
  const [artworks, setArtworks] = useState<Artwork[]>([])
  const [overview, setOverview] = useState<Overview | null>(null)
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [storageBackend, setStorageBackend] = useState('local')
  const [loading, setLoading] = useState(false)
  const [toast, setToast] = useState('')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Artwork | null>(null)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  const notify = useCallback((message: string) => {
    setToast(message)
    window.setTimeout(() => setToast(''), 4000)
  }, [])

  const loadData = useCallback(async (query = '', archived = false) => {
    setLoading(true)
    try {
      const [vault, stats, activity, health] = await Promise.all([
        request<{ artworks: Artwork[] }>(`/artworks?${new URLSearchParams({ ...(query ? { q: query } : {}), archived: String(archived) })}`, csrfToken),
        request<Overview>('/analytics/overview', csrfToken),
        request<{ events: AuditEvent[] }>('/audit-logs', csrfToken),
        request<{ status: string; storage: string }>('/health'),
      ])
      setArtworks(vault.artworks)
      setOverview(stats)
      setEvents(activity.events)
      setStorageBackend(health.storage)
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not load workspace data.')
    } finally {
      setLoading(false)
    }
  }, [csrfToken, notify])

  useEffect(() => {
    request<{ user: User; workspace: string; csrf_token: string }>('/auth/me')
      .then((result) => {
        setUser(result.user)
        setWorkspaceName(result.workspace)
        setCsrfToken(result.csrf_token)
      })
      .catch(() => setUser(null))
  }, [])

  useEffect(() => {
    if (user) void loadData()
  }, [user, loadData])

  useEffect(() => {
    if (!user) return
    const refresh = () => {
      if (view !== 'vault' && document.visibilityState === 'visible') void loadData()
    }
    const interval = window.setInterval(refresh, 30_000)
    document.addEventListener('visibilitychange', refresh)
    return () => {
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', refresh)
    }
  }, [user, view, loadData])

  const onSearch = async (value: string) => {
    setSearch(value)
    if (view !== 'vault') setView('vault')
    await loadData(value.trim())
  }

  const logout = async () => {
    try {
      await request('/auth/logout', csrfToken, { method: 'POST' })
      setUser(null)
      setCsrfToken('')
      setArtworks([])
      setOverview(null)
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Unable to sign out.')
    }
  }

  if (user === undefined) {
    return <div className="loading-screen"><span className="brand-mark"><Shield size={21} /></span><LoaderCircle className="spin" size={20} /></div>
  }
  if (!user) {
    return <AuthScreen onAuthenticated={(nextUser, token, workspace) => { setUser(nextUser); setCsrfToken(token); setWorkspaceName(workspace) }} />
  }

  const navigate = (next: string) => {
    setView(next)
    setMobileNavOpen(false)
    if (next === 'vault') void loadData(search)
  }

  return (
    <div className="app-shell">
      {mobileNavOpen && <button className="nav-scrim" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)} />}
      <aside className={`sidebar ${mobileNavOpen ? 'sidebar-open' : ''}`}>
        <div className="brand"><span className="brand-mark"><Shield size={19} strokeWidth={2.3} /></span><span>artlock</span><span className="brand-beta">VAULT</span></div>
        <div className="workspace-switcher">
          <div className="workspace-avatar">S</div>
          <div className="workspace-copy"><strong>{workspaceName}</strong><span>Private workspace</span></div>
          <ChevronDown size={15} />
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav className="primary-nav" aria-label="Main navigation">
          {navItems.map(({ id, label, icon: Icon }) => (
            <button key={id} className={`nav-item ${view === id ? 'active' : ''}`} onClick={() => navigate(id)}>
              <Icon size={17} strokeWidth={1.8} /><span>{label}</span>
              {id === 'vault' && <span className="nav-count">{overview?.total_artworks ?? 0}</span>}
            </button>
          ))}
        </nav>
        <div className="nav-divider" />
        <div className="nav-label">PREFERENCES</div>
        <button className={`nav-item ${view === 'settings' ? 'active' : ''}`} onClick={() => navigate('settings')}><Settings size={17} /><span>Settings</span></button>
        <button className="nav-item" onClick={() => notify('Help documentation is coming soon.')}><CircleHelp size={17} /><span>Help & documentation</span></button>
        <div className="sidebar-bottom">
          <div className="storage-mini">
            <div className="storage-mini-title"><span>Storage used</span><span>{formatBytes(overview?.total_storage_bytes ?? 0)}</span></div>
            <div className="storage-note">Application-calculated usage</div>
          </div>
          <button className="profile-card" onClick={() => void logout()}>
            <span className="profile-avatar">{user.display_name.charAt(0).toUpperCase()}</span>
            <span className="profile-copy"><strong>{user.display_name}</strong><span>{user.email}</span></span>
            <LogOut size={16} aria-label="Sign out" />
          </button>
        </div>
      </aside>

      <main className="main-shell">
        <header className="topbar">
          <button className="icon-button mobile-menu" aria-label="Open menu" onClick={() => setMobileNavOpen(true)}><Menu size={19} /></button>
          <div className="breadcrumbs"><span>{workspaceName}</span><span className="crumb-separator">/</span><strong>{navItems.find((item) => item.id === view)?.label ?? (view === 'settings' ? 'Settings' : 'Artwork vault')}</strong></div>
          <div className="topbar-actions">
            <label className="global-search"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void onSearch(search) }} placeholder="Search your vault..." /><kbd>↵</kbd></label>
            <button className="icon-button notification-button" aria-label="Notifications" onClick={() => notify('You’re all caught up.')}><Bell size={18} /><i /></button>
            <button className="top-avatar" onClick={() => void logout()} title="Sign out">{user.display_name.charAt(0).toUpperCase()}</button>
          </div>
        </header>

        <div className="page-content">
          {view === 'overview' && <OverviewPage overview={overview} events={events} loading={loading} onNavigate={navigate} onNew={() => setUploadOpen(true)} todayLabel={todayLabel} />}
          {view === 'vault' && <VaultPage artworks={artworks} loading={loading} onOpen={setSelected} onNew={() => setUploadOpen(true)} onRefresh={(archived) => void loadData(search, archived)} onSearch={onSearch} search={search} setSearch={setSearch} csrfToken={csrfToken} notify={notify} />}
          {view === 'verification' && <VerificationPage artworks={artworks} csrfToken={csrfToken} notify={notify} />}
          {view === 'activity' && <ActivityPage events={events} />}
          {view === 'settings' && <SettingsPage user={user} backend={storageBackend} />}
        </div>
      </main>

      {uploadOpen && <UploadDialog csrfToken={csrfToken} onClose={() => setUploadOpen(false)} onCreated={(artwork) => { setUploadOpen(false); notify('Artwork registered and encrypted successfully.'); setView('vault'); setSelected(artwork); void loadData() }} />}
      {selected && <ArtworkDialog artwork={selected} csrfToken={csrfToken} notify={notify} onClose={() => setSelected(null)} />}
      {toast && <div className="toast" role="status"><Check size={16} />{toast}<button aria-label="Dismiss notification" onClick={() => setToast('')}><X size={15} /></button></div>}
    </div>
  )
}

function AuthScreen({ onAuthenticated }: { onAuthenticated: (user: User, token: string, workspace: string) => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [workspaceName, setWorkspaceName] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      const result = await request<{ user: User; csrf_token: string; workspace: string }>(
        `/auth/${mode === 'login' ? 'login' : 'register'}`,
        '',
        {
          method: 'POST',
          body: JSON.stringify(mode === 'login'
            ? { email, password }
            : { email, password, display_name: displayName, workspace_name: workspaceName }),
        },
      )
      onAuthenticated(result.user, result.csrf_token, result.workspace)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Authentication failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-art">
        <div className="auth-top-brand"><span className="brand-mark"><Shield size={19} /></span><span>artlock</span></div>
        <div className="auth-visual">
          <div className="auth-orbit orbit-one" /><div className="auth-orbit orbit-two" />
          <div className="auth-art-card"><div className="art-card-sun" /><div className="art-card-mountain mountain-a" /><div className="art-card-mountain mountain-b" /><div className="art-card-water" /><span className="art-card-label">ARTLOCK · VAULT</span></div>
          <span className="floating-seal"><Fingerprint size={21} /><span>SHA-256<br /><b>FILE INTEGRITY</b></span></span>
          <span className="floating-lock"><ShieldCheck size={20} /></span>
        </div>
        <div className="auth-tagline"><p>YOUR WORK.<br /><em>YOUR RECORD.</em></p><span>Securely register, protect, and verify your digital creations.</span></div>
        <div className="auth-footnote"><span>PRIVATE BY DESIGN</span><span>ENCRYPTED STORAGE</span><span>INTEGRITY FIRST</span></div>
      </div>
      <div className="auth-panel">
        <div className="auth-mobile-brand"><span className="brand-mark"><Shield size={18} /></span>artlock</div>
        <form className="auth-form" onSubmit={(event) => void submit(event)}>
          <span className="eyebrow">ARTWORK OWNERSHIP & INTEGRITY VAULT</span>
          <h1>{mode === 'login' ? 'Welcome back' : 'Create your vault'}</h1>
          <p className="auth-subtitle">{mode === 'login' ? 'Sign in to access your secure workspace.' : 'Start protecting your creative work today.'}</p>
          {mode === 'register' && <>
            <label className="field-label">Your name<input required value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="e.g. Alex Morgan" autoComplete="name" /></label>
            <label className="field-label">Workspace name<input value={workspaceName} onChange={(event) => setWorkspaceName(event.target.value)} placeholder="e.g. Morgan Studio" /></label>
          </>}
          <label className="field-label">Email address<input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@studio.com" autoComplete="email" /></label>
          <label className="field-label">Password<input required type="password" minLength={mode === 'register' ? 12 : undefined} value={password} onChange={(event) => setPassword(event.target.value)} placeholder={mode === 'register' ? 'At least 12 characters' : 'Enter your password'} autoComplete={mode === 'register' ? 'new-password' : 'current-password'} /></label>
          {error && <div className="form-error"><ShieldAlert size={16} />{error}</div>}
          <button className="button button-primary auth-submit" disabled={busy}>{busy ? <LoaderCircle className="spin" size={17} /> : null}{mode === 'login' ? 'Sign in securely' : 'Create secure workspace'}<ArrowRight size={16} /></button>
          <div className="auth-switch">{mode === 'login' ? 'New to ArtLock?' : 'Already have an account?'} <button type="button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>{mode === 'login' ? 'Create an account' : 'Sign in'}</button></div>
          <div className="auth-security"><ShieldCheck size={16} /><span>Your files are encrypted before storage. Your private work stays private.</span></div>
        </form>
      </div>
    </div>
  )
}

function OverviewPage({
  overview, events, loading, onNavigate, onNew,
  todayLabel,
}: {
  overview: Overview | null
  events: AuditEvent[]
  loading: boolean
  onNavigate: (view: string) => void
  onNew: () => void
  todayLabel: string
}) {
  const trend = overview?.registration_trend ?? []
  const topTypes = Object.entries(overview?.by_type ?? {}).sort((a, b) => b[1] - a[1]).slice(0, 4)
  const verificationTotal = (overview?.verified ?? 0) + (overview?.mismatches ?? 0)
  const matchingPercent = verificationTotal ? (overview?.verified ?? 0) / verificationTotal * 100 : 0
  const mismatchPercent = verificationTotal ? (overview?.mismatches ?? 0) / verificationTotal * 100 : 0
  const fileTypes = Object.entries(overview?.by_type ?? {}).map(([name, value]) => ({
    name: name.split('/')[1]?.toUpperCase() ?? name,
    value,
  }))
  return (
    <>
      <div className="page-heading heading-row">
        <div><span className="eyebrow">{todayLabel}</span><h1>Good to see you.</h1><p>Your creative work, protected in one place.</p></div>
        <button className="button button-primary" onClick={onNew}><Plus size={17} />Register artwork</button>
      </div>
      <div className="metric-grid">
        <MetricCard label="Registered artworks" value={loading ? '—' : String(overview?.total_artworks ?? 0)} note="Across your workspace" icon={<FileImage size={17} />} accent="violet" />
        <MetricCard label="Integrity checks" value={loading ? '—' : String(overview?.total_verifications ?? 0)} note={`${overview?.verified ?? 0} matches · ${overview?.mismatches ?? 0} mismatches`} icon={<ShieldCheck size={17} />} accent="green" />
        <MetricCard label="Favorites" value={loading ? '—' : String(overview?.favorite_count ?? 0)} note="Starred in your vault" icon={<Star size={17} />} accent="amber" />
        <MetricCard label="Storage in use" value={loading ? '—' : formatBytes(overview?.total_storage_bytes ?? 0)} note="Application-calculated" icon={<Gauge size={17} />} accent="blue" />
      </div>
      <div className="dashboard-grid">
        <section className="panel trend-panel">
          <div className="panel-heading"><div><h2>Registration activity</h2><p>Artwork added to your vault over time</p></div><span className="range-pill">Last 14 days</span></div>
          <div className="chart-wrap">
            {trend.some((point) => point.registrations > 0)
              ? <Suspense fallback={<div className="chart-empty">Loading chart…</div>}><RegistrationChart data={trend} /></Suspense>
              : <div className="chart-empty"><div className="empty-chart-icon"><AreaChartIcon /></div><strong>Your activity begins here</strong><span>Register your first artwork to see your vault grow.</span><button className="text-button" onClick={onNew}>Register artwork <ArrowRight size={14} /></button></div>}
          </div>
        </section>
        <section className="panel integrity-panel">
          <div className="panel-heading"><div><h2>Integrity overview</h2><p>Results from actual file comparisons</p></div><Fingerprint size={17} className="subtle-icon" /></div>
          <div className="integrity-score"><div className="score-ring" style={{ background: verificationTotal ? `conic-gradient(#6fcba4 0 ${matchingPercent}%, #ca9b5b ${matchingPercent}% ${matchingPercent + mismatchPercent}%, #292d38 ${matchingPercent + mismatchPercent}% 100%)` : '#292d38' }}><div><strong>{overview?.verified ?? 0}</strong><span>matches</span></div></div><div className="score-legend"><span><i className="legend-dot dot-green" />Matching files <b>{overview?.verified ?? 0}</b></span><span><i className="legend-dot dot-amber" />Mismatches <b>{overview?.mismatches ?? 0}</b></span></div></div>
          <button className="panel-link" onClick={() => onNavigate('verification')}>Run a verification <ArrowRight size={15} /></button>
        </section>
        <section className="panel recent-panel">
          <div className="panel-heading"><div><h2>Recently registered</h2><p>Your latest additions</p></div><button className="text-button" onClick={() => onNavigate('vault')}>View vault <ArrowRight size={14} /></button></div>
          {overview?.recent.length ? <div className="recent-list">{overview.recent.slice(0, 4).map((item) => <div className="recent-row" key={item.id}><span className="file-icon"><FileImage size={17} /></span><span className="recent-info"><strong>{item.title}</strong><small>{item.filename}</small></span><span className="recent-size">{formatBytes(item.file_size)}</span><span className="hash-status"><ShieldCheck size={14} /> Registered</span></div>)}</div> : <div className="inline-empty"><ImagePlus size={19} /><span>No artwork registered yet.</span></div>}
        </section>
        <section className="panel activity-panel">
          <div className="panel-heading"><div><h2>Security activity</h2><p>Recent actions in this workspace</p></div><button className="icon-button small" aria-label="View all activity" onClick={() => onNavigate('activity')}><ArrowRight size={16} /></button></div>
          {events.length ? <div className="event-list">{events.slice(0, 4).map((event) => <div className="event-row" key={event.id}><span className={`event-dot ${event.outcome === 'mismatch' ? 'warning' : ''}`} /><div><strong>{event.action.replaceAll('.', ' ')}</strong><span>{event.actor} · {formatDate(event.created_at)}</span></div></div>)}</div> : <div className="inline-empty"><Shield size={18} /><span>Activity is recorded as you use the vault.</span></div>}
        </section>
        <section className="panel category-panel">
          <div className="panel-heading"><div><h2>Category mix</h2><p>Distribution by assigned category</p></div><FolderOpen size={17} className="subtle-icon" /></div>
          <div className="category-bars">{overview?.categories.length ? overview.categories.map((category, index) => {
            const total = overview.categories.reduce((sum, item) => sum + item.count, 0)
            return <div className="category-bar-row" key={category.name}><div><span>{category.name}</span><b>{category.count}</b></div><i><span className={`category-fill fill-${index % 5}`} style={{ width: `${total ? category.count / total * 100 : 0}%` }} /></i></div>
          }) : <div className="inline-empty">Categories appear as you organize artwork.</div>}</div>
          <button className="panel-link" onClick={() => onNavigate('vault')}>Organize your artwork <ArrowRight size={15} /></button>
        </section>
        <section className="panel operations-panel">
          <div className="panel-heading"><div><h2>Workspace operations</h2><p>Real actions and integrity activity</p></div><ShieldCheck size={17} className="subtle-icon" /></div>
          <div className="operation-stats"><div><strong>{overview?.versions_count ?? 0}</strong><span>Preserved versions</span></div><div><strong>{overview?.total_artworks ?? 0}</strong><span>Active records</span></div></div>
          <div className="operation-latest">{overview?.latest_verification ? <><span className={`latest-result ${overview.latest_verification.result === 'MATCH' ? 'good' : 'bad'}`} />Latest comparison <b>{overview.latest_verification.result}</b><small>{formatDate(overview.latest_verification.created_at)}</small></> : <><span className="latest-result" />No verification run yet</>}</div>
          <a className="panel-link export-link" href="/api/v1/analytics/inventory.csv">Export authorized inventory <ArrowRight size={15} /></a>
        </section>
        <section className="panel storage-panel">
          <div className="panel-heading"><div><h2>Storage trajectory</h2><p>Registered file bytes over the last 14 days</p></div><span className="range-pill">{formatBytes(overview?.total_storage_bytes ?? 0)} total</span></div>
          <div className="secondary-chart">{overview?.storage_trend?.length ? <Suspense fallback={<div className="chart-empty">Loading chart…</div>}><StorageTrend data={overview.storage_trend} /></Suspense> : <div className="chart-empty">Storage history will appear as artwork is registered.</div>}</div>
        </section>
        <section className="panel filetype-panel">
          <div className="panel-heading"><div><h2>File composition</h2><p>Active assets by detected file format</p></div><FileImage size={17} className="subtle-icon" /></div>
          {fileTypes.length ? <Suspense fallback={<div className="chart-empty">Loading chart…</div>}><FileTypeDonut data={fileTypes} /></Suspense> : <div className="inline-empty">No file types to visualize yet.</div>}
        </section>
      </div>
      <div className="dashboard-footnote"><ShieldCheck size={14} /><span>SHA-256 confirms byte-level equality with a registered file. It is not proof of copyright ownership or authorship.</span></div>
      <div className="type-strip"><span>FILE TYPES</span>{topTypes.length ? topTypes.map(([type, count]) => <span className="type-chip" key={type}>{type.replace('image/', '').replace('application/', '').toUpperCase()} <b>{count}</b></span>) : <span className="type-none">No files registered</span>}</div>
    </>
  )
}

function MetricCard({ label, value, note, icon, accent }: { label: string; value: string; note: string; icon: React.ReactNode; accent: string }) {
  return <section className={`metric-card accent-${accent}`}><div className="metric-top"><span>{label}</span><i>{icon}</i></div><strong className="metric-value">{value}</strong><span className="metric-note">{note}</span></section>
}

function VaultPage({
  artworks, loading, onOpen, onNew, onRefresh, onSearch, search, setSearch, csrfToken, notify,
}: {
  artworks: Artwork[]
  loading: boolean
  onOpen: (artwork: Artwork) => void
  onNew: () => void
  onRefresh: (archived?: boolean) => void
  onSearch: (value: string) => void
  search: string
  setSearch: (value: string) => void
  csrfToken: string
  notify: (message: string) => void
}) {
  const [archived, setArchived] = useState(false)
  const [favoritesOnly, setFavoritesOnly] = useState(false)
  const [typeFilter, setTypeFilter] = useState('all')
  const [sort, setSort] = useState<'newest' | 'oldest' | 'name' | 'size'>('newest')
  const visible = useMemo(() => artworks
    .filter((item) => item.archived === archived)
    .filter((item) => !favoritesOnly || item.favorite)
    .filter((item) => typeFilter === 'all' || item.content_type === typeFilter)
    .sort((first, second) => sort === 'name'
      ? first.title.localeCompare(second.title)
      : sort === 'oldest'
        ? first.created_at.localeCompare(second.created_at)
        : sort === 'size'
          ? second.file_size - first.file_size
          : second.created_at.localeCompare(first.created_at)),
  [artworks, archived, favoritesOnly, sort, typeFilter])

  const archive = async (event: React.MouseEvent, item: Artwork) => {
    event.stopPropagation()
    try {
      await request(`/artworks/${item.id}/archive`, csrfToken, { method: 'POST' })
      notify(item.archived ? 'Artwork restored to your vault.' : 'Artwork archived.')
      onRefresh(archived)
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not update artwork.')
    }
  }

  const toggleFavorite = async (event: React.MouseEvent, artwork: Artwork) => {
    event.stopPropagation()
    try {
      await request(`/artworks/${artwork.id}`, csrfToken, {
        method: 'PATCH',
        body: JSON.stringify({ favorite: !artwork.favorite }),
      })
      notify(artwork.favorite ? 'Removed from favorites.' : 'Added to favorites.')
      onRefresh(archived)
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not update favorite.')
    }
  }

  return <>
    <div className="page-heading heading-row vault-heading"><div><span className="eyebrow">YOUR CREATIVE ARCHIVE</span><h1>Artwork vault</h1><p>Securely registered originals and their integrity records.</p></div><button className="button button-primary" onClick={onNew}><Plus size={17} />Register artwork</button></div>
    <div className="vault-toolbar">
      <div className="vault-tabs"><button className={!archived ? 'selected' : ''} onClick={() => { setArchived(false); onRefresh(false) }}>All artwork</button><button className={archived ? 'selected' : ''} onClick={() => { setArchived(true); onRefresh(true) }}>Archived</button></div>
      <div className="vault-controls"><form className="vault-search" onSubmit={(event) => { event.preventDefault(); onSearch(search) }}><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search artwork..." /><button aria-label="Search"><ArrowRight size={14} /></button></form><button className={`filter-chip ${favoritesOnly ? 'filter-active' : ''}`} onClick={() => setFavoritesOnly(!favoritesOnly)}><Star size={13} />Favorites</button><select className="filter-select" aria-label="Filter by file type" value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}><option value="all">All types</option>{[...new Set(artworks.map((item) => item.content_type))].map((type) => <option key={type} value={type}>{type.split('/')[1]?.toUpperCase()}</option>)}</select><select className="filter-select" aria-label="Sort artwork" value={sort} onChange={(event) => setSort(event.target.value as typeof sort)}><option value="newest">Newest</option><option value="oldest">Oldest</option><option value="name">Name</option><option value="size">Largest</option></select><span className="result-count">{visible.length} {visible.length === 1 ? 'file' : 'files'}</span></div>
    </div>
    {loading ? <div className="asset-grid">{[0, 1, 2, 3].map((item) => <div className="asset-skeleton" key={item}><div /><span /><i /></div>)}</div> : visible.length ? <div className="asset-grid">{visible.map((item) => <article className="asset-card" key={item.id} onClick={() => onOpen(item)} tabIndex={0} onKeyDown={(event) => { if (event.key === 'Enter') onOpen(item) }}>
      <div className={`asset-cover ${item.content_type.startsWith('image/') ? 'image-preview' : 'document-preview'}`}>{item.content_type.startsWith('image/') ? <img src={`/api/v1/artworks/${item.id}/preview`} alt={`Preview of ${item.title}`} loading="lazy" /> : <><span className="document-preview-icon"><FileImage size={24} /></span><span className="document-preview-label">PDF DOCUMENT</span></>}<span className="asset-file-label">{item.content_type.split('/')[1]?.toUpperCase()}</span></div>
      <div className="asset-info"><div className="asset-title-row"><strong title={item.title}>{item.title}</strong><div className="asset-card-actions"><button className={`icon-button favorite-button ${item.favorite ? 'is-favorite' : ''}`} onClick={(event) => void toggleFavorite(event, item)} aria-label={item.favorite ? 'Remove from favorites' : 'Add to favorites'}><Star size={14} fill={item.favorite ? 'currentColor' : 'none'} /></button><button className="icon-button asset-menu" onClick={(event) => void archive(event, item)} aria-label={item.archived ? 'Restore artwork' : 'Archive artwork'}>{item.archived ? <ArrowRight size={15} /> : <MoreHorizontal size={16} />}</button></div></div><span className="asset-filename">{item.filename}</span><div className="asset-meta"><span>{formatBytes(item.file_size)}</span><span className="meta-separator">·</span><span>{formatDate(item.created_at)}</span><span className="version-pill">v{item.version_number}</span></div><div className="asset-hash"><ShieldCheck size={13} /><span>SHA-256 registered</span><span className="asset-category">{item.category}</span></div></div>
    </article>)}</div> : <div className="empty-vault"><div className="empty-vault-icon"><FolderOpen size={23} /></div><h2>{search ? 'No matching artwork' : archived ? 'Nothing archived' : 'Your vault is ready'}</h2><p>{search ? 'Try another title or filename.' : archived ? 'Archived artwork will appear here.' : 'Register your first original to create its SHA-256 integrity record.'}</p>{!search && !archived && <button className="button button-primary" onClick={onNew}><Plus size={16} />Register your first artwork</button>}</div>}
  </>
}

function VerificationPage({ artworks, csrfToken, notify }: { artworks: Artwork[]; csrfToken: string; notify: (message: string) => void }) {
  const [artworkId, setArtworkId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [result, setResult] = useState<Verification | null>(null)
  const [busy, setBusy] = useState(false)
  const selectedArtwork = artworks.find((item) => item.id === artworkId)
  const verify = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!artworkId || !file) return
    setBusy(true)
    setResult(null)
    const body = new FormData()
    body.append('file', file)
    try {
      const response = await request<Verification>(`/artworks/${artworkId}/verify`, csrfToken, { method: 'POST', body })
      setResult(response)
      notify(response.result === 'MATCH' ? 'Integrity check complete: file matches.' : 'Integrity check complete: file differs.')
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Verification could not be completed.')
    } finally {
      setBusy(false)
    }
  }
  return <>
    <div className="page-heading"><span className="eyebrow">CRYPTOGRAPHIC INTEGRITY</span><h1>Verify artwork</h1><p>Compare a file’s actual bytes against its registered SHA-256 fingerprint.</p></div>
    <div className="verification-layout">
      <form className="panel verify-form" onSubmit={(event) => void verify(event)}>
        <div className="verify-intro-icon"><Fingerprint size={21} /></div><h2>Run an integrity check</h2><p>Select a registered artwork and the file you want to compare. The comparison runs securely on the server.</p>
        <label className="field-label">Registered artwork<select required value={artworkId} onChange={(event) => setArtworkId(event.target.value)}><option value="">Choose from your vault</option>{artworks.filter((item) => !item.archived).map((item) => <option key={item.id} value={item.id}>{item.title} — {item.filename}</option>)}</select></label>
        {selectedArtwork && <div className="registered-hash"><span>REGISTERED SHA-256</span><code>{selectedArtwork.sha256}</code></div>}
        <label className="field-label">File to compare<input required type="file" accept=".png,.jpg,.jpeg,.webp,.pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
        <button className="button button-primary full-width" disabled={busy || !artworkId || !file}>{busy ? <LoaderCircle className="spin" size={16} /> : <FileSearch size={16} />}Compare file</button>
        <div className="verify-disclaimer"><Shield size={15} /><span>A match confirms byte-for-byte equality with the stored reference. It does not establish authorship or ownership.</span></div>
      </form>
      <section className="panel verification-result">
        {result ? <><div className={`result-badge ${result.result === 'MATCH' ? 'match' : 'mismatch'}`}>{result.result === 'MATCH' ? <ShieldCheck size={26} /> : <ShieldAlert size={26} />}</div><span className="eyebrow">COMPARISON COMPLETE</span><h2>{result.result === 'MATCH' ? 'Files match' : 'Files are different'}</h2><p>{result.result === 'MATCH' ? 'The uploaded file has the same SHA-256 fingerprint as the registered artwork.' : 'The uploaded file does not match the registered artwork bytes.'}</p><div className="hash-comparison"><HashValue label="Registered fingerprint" value={result.registered_sha256} /><div className="hash-divider" /><HashValue label="Calculated fingerprint" value={result.calculated_sha256} /></div><span className="verified-time">Verified {formatDate(result.verified_at)}</span></> : <><div className="result-placeholder"><Fingerprint size={31} /></div><h2>Verification results</h2><p>After comparison, the genuine result and both SHA-256 values will appear here.</p><div className="result-placeholder-note"><ShieldCheck size={15} /><span>No simulated results. Every comparison uses the uploaded file bytes.</span></div></>}
      </section>
    </div>
  </>
}

function HashValue({ label, value }: { label: string; value: string }) {
  return <div className="hash-value"><span>{label}</span><code>{value}</code></div>
}

function ActivityPage({ events }: { events: AuditEvent[] }) {
  return <><div className="page-heading"><span className="eyebrow">WORKSPACE HISTORY</span><h1>Activity & audit</h1><p>Application-recorded activity for your private workspace.</p></div><section className="panel audit-panel"><div className="panel-heading"><div><h2>Recent events</h2><p>{events.length} latest recorded actions</p></div><span className="range-pill">Audit trail</span></div>{events.length ? <div className="audit-table"><div className="audit-table-head"><span>EVENT</span><span>ACTOR</span><span>OUTCOME</span><span>TIME</span></div>{events.map((item) => <div className="audit-table-row" key={item.id}><span className="audit-action"><i className={item.outcome === 'mismatch' ? 'event-dot warning' : 'event-dot'} />{item.action.replaceAll('.', ' ')}</span><span>{item.actor}</span><span><b className={`outcome-pill ${item.outcome === 'mismatch' ? 'outcome-warning' : ''}`}>{item.outcome}</b></span><span>{new Date(item.created_at).toLocaleString()}</span></div>)}</div> : <div className="inline-empty"><Clock3 size={18} /><span>Important workspace actions will be recorded here.</span></div>}<div className="audit-footnote"><Shield size={14} />This is an application audit trail, not tamper-proof external logging.</div></section></>
}

function SettingsPage({ user, backend }: { user: User; backend: string }) {
  return <><div className="page-heading"><span className="eyebrow">WORKSPACE PREFERENCES</span><h1>Settings</h1><p>Account and storage configuration for your ArtLock workspace.</p></div><div className="settings-grid"><section className="panel setting-panel"><div className="setting-icon"><Settings size={18} /></div><div><h2>Account profile</h2><p>Your signed-in workspace account.</p></div><dl><div><dt>Display name</dt><dd>{user.display_name}</dd></div><div><dt>Email address</dt><dd>{user.email}</dd></div><div><dt>Session security</dt><dd><span className="status-dot" />HTTP-only session cookie</dd></div></dl></section><section className="panel setting-panel"><div className="setting-icon"><ShieldCheck size={18} /></div><div><h2>Storage & encryption</h2><p>Current application storage configuration.</p></div><dl><div><dt>Storage backend</dt><dd><span className="status-dot" />{backend === 's3' ? 'Private Amazon S3' : 'Local encrypted storage'}</dd></div><div><dt>Artwork encryption</dt><dd>AES-256-GCM at application layer</dd></div><div><dt>Identity digest</dt><dd>SHA-256 of original plaintext bytes</dd></div></dl><p className="setting-note">Storage usage shown in ArtLock is calculated from registered file metadata. It is not an AWS billing or S3 service metric.</p></section></div><div className="settings-callout"><Shield size={16} /><span>Production deployment requires unique secret keys, HTTPS, a private S3 bucket, and a managed secrets provider.</span></div></>
}

function UploadDialog({ csrfToken, onClose, onCreated }: { csrfToken: string; onClose: () => void; onCreated: (artwork: Artwork) => void }) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('Illustration')
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!file) { setError('Choose a file to register.'); return }
    const body = new FormData()
    body.set('title', title)
    body.set('description', description)
    body.set('category', category)
    body.set('file', file)
    setBusy(true)
    setError('')
    try {
      const response = await request<{ artwork: Artwork }>('/artworks', csrfToken, { method: 'POST', body })
      onCreated(response.artwork)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Upload could not be completed.')
    } finally {
      setBusy(false)
    }
  }
  return <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}><section className="modal upload-modal" role="dialog" aria-modal="true" aria-labelledby="upload-title"><div className="modal-header"><div><span className="eyebrow">NEW VAULT ENTRY</span><h2 id="upload-title">Register artwork</h2></div><button className="icon-button" aria-label="Close" onClick={onClose}><X size={19} /></button></div><p className="modal-description">Your original file will be validated, fingerprinted, encrypted, and securely stored.</p><form onSubmit={(event) => void submit(event)}><label className="field-label">Artwork title<input required maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Give your artwork a name" /></label><label className="field-label">Category<select value={category} onChange={(event) => setCategory(event.target.value)}>{['Illustration', 'Photography', 'Graphic design', 'Digital painting', '3D art', 'Document', 'Uncategorized'].map((option) => <option key={option}>{option}</option>)}</select></label><label className="field-label">Description <span className="optional-label">OPTIONAL</span><textarea maxLength={4000} rows={3} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Add context or notes about this work..." /></label><label className={`dropzone ${file ? 'file-selected' : ''}`}><input type="file" required accept=".png,.jpg,.jpeg,.webp,.pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /><span className="drop-icon">{file ? <Check size={19} /> : <Upload size={19} />}</span><strong>{file ? file.name : 'Choose a file to upload'}</strong><small>{file ? `${formatBytes(file.size)} · Ready to register` : 'PNG, JPEG, WebP, PDF · Up to 25 MB'}</small></label>{error && <div className="form-error"><ShieldAlert size={16} />{error}</div>}<div className="modal-footer"><span><ShieldCheck size={15} />AES-256-GCM encrypted</span><button className="button button-primary" disabled={busy}>{busy ? <LoaderCircle className="spin" size={16} /> : <Fingerprint size={16} />}Register securely</button></div></form></section></div>
}

function ArtworkDialog({ artwork: initialArtwork, csrfToken, notify, onClose }: { artwork: Artwork; csrfToken: string; notify: (message: string) => void; onClose: () => void }) {
  const [artwork, setArtwork] = useState(initialArtwork)
  const [editTitle, setEditTitle] = useState(initialArtwork.title)
  const [editDescription, setEditDescription] = useState(initialArtwork.description)
  const [editCategory, setEditCategory] = useState(initialArtwork.category)
  const [editTags, setEditTags] = useState(initialArtwork.tags.join(', '))
  const [versionFile, setVersionFile] = useState<File | null>(null)
  const [versionNotes, setVersionNotes] = useState('')
  const [verification, setVerification] = useState<Verification | null>(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    request<{ artwork: Artwork }>(`/artworks/${initialArtwork.id}`, csrfToken)
      .then((response) => {
        setArtwork(response.artwork)
        setEditTitle(response.artwork.title)
        setEditDescription(response.artwork.description)
        setEditCategory(response.artwork.category)
        setEditTags(response.artwork.tags.join(', '))
      })
      .catch((error: unknown) => notify(error instanceof Error ? error.message : 'Could not load artwork details.'))
  }, [csrfToken, initialArtwork.id, notify])
  const saveMetadata = async () => {
    try {
      const result = await request<{ artwork: Artwork }>(`/artworks/${artwork.id}`, csrfToken, {
        method: 'PATCH',
        body: JSON.stringify({
          title: editTitle,
          description: editDescription,
          category: editCategory,
          tags: editTags.split(',').map((tag) => tag.trim()).filter(Boolean),
        }),
      })
      setArtwork(result.artwork)
      notify('Artwork details saved.')
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not save artwork details.')
    }
  }
  const addVersion = async () => {
    if (!versionFile) { notify('Choose the file for your new version.'); return }
    const body = new FormData()
    body.set('file', versionFile)
    body.set('notes', versionNotes)
    setBusy(true)
    try {
      await request(`/artworks/${artwork.id}/versions`, csrfToken, { method: 'POST', body })
      notify('New version added. Previous versions remain preserved.')
      setVersionFile(null)
      setVersionNotes('')
      const response = await request<{ artwork: Artwork }>(`/artworks/${artwork.id}`, csrfToken)
      setArtwork(response.artwork)
    } catch (error) {
      notify(error instanceof Error ? error.message : 'Could not add version.')
    } finally {
      setBusy(false)
    }
  }
  return <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}><section className="modal detail-modal" role="dialog" aria-modal="true" aria-labelledby="detail-title"><div className="modal-header"><div><span className="eyebrow">ARTWORK RECORD</span><h2 id="detail-title">{artwork.title}</h2></div><button className="icon-button" aria-label="Close" onClick={onClose}><X size={19} /></button></div><div className="detail-file-banner"><span className="file-icon large"><FileImage size={22} /></span><span><strong>{artwork.filename}</strong><small>{formatBytes(artwork.file_size)} · {artwork.content_type}</small></span><span className="version-pill">v{artwork.version_number}</span></div><div className="metadata-editor"><label className="field-label">Title<input maxLength={200} value={editTitle} onChange={(event) => setEditTitle(event.target.value)} /></label><label className="field-label">Category<input maxLength={80} value={editCategory} onChange={(event) => setEditCategory(event.target.value)} /></label><label className="field-label">Tags <span className="optional-label">COMMA SEPARATED</span><input value={editTags} onChange={(event) => setEditTags(event.target.value)} placeholder="portfolio, client, 2026" /></label><label className="field-label">Description<textarea rows={2} maxLength={4000} value={editDescription} onChange={(event) => setEditDescription(event.target.value)} /></label><button className="button button-secondary metadata-save" onClick={() => void saveMetadata()}><Check size={14} />Save details</button></div><div className="detail-hash"><span>REGISTERED SHA-256 · PLAINTEXT</span><code>{artwork.sha256}</code><small>This digest verifies byte-level equality, not ownership or authorship.</small></div><div className="detail-actions"><a className="button button-secondary" href={`/api/v1/artworks/${artwork.id}/download`}><ArrowDownToLine size={16} />Download original</a><label className="button button-secondary verify-upload-button"><FileSearch size={15} />{verification ? verification.result : 'Verify file'}<input type="file" accept=".png,.jpg,.jpeg,.webp,.pdf" onChange={async (event) => { const file = event.target.files?.[0]; if (!file) return; const body = new FormData(); body.set('file', file); try { const result = await request<Verification>(`/artworks/${artwork.id}/verify`, csrfToken, { method: 'POST', body }); setVerification(result); notify(result.result === 'MATCH' ? 'File matches the registered original.' : 'File differs from the registered original.') } catch (error) { notify(error instanceof Error ? error.message : 'Could not verify this file.') } }} /></label></div><div className="version-section"><div className="panel-heading"><div><h3>Version history</h3><p>Each version keeps its own fingerprint and record.</p></div></div><div className="version-timeline">{(artwork.versions ?? []).map((version) => <div className={`version-row ${version.version_number === artwork.version_number ? 'current-version' : ''}`} key={version.id}><span className="timeline-node" /><span className="version-number">v{version.version_number}</span><span className="version-details"><strong>{version.filename}</strong><small>{version.notes || 'No change notes'}</small></span><span className="version-date">{formatDate(version.created_at)}</span></div>)}</div><div className="new-version-form"><div><strong>Add a new version</strong><span>Previous versions will not be overwritten.</span></div><label className="version-file-input"><input type="file" accept=".png,.jpg,.jpeg,.webp,.pdf" onChange={(event) => setVersionFile(event.target.files?.[0] ?? null)} /><Upload size={14} />{versionFile ? versionFile.name : 'Choose file'}</label><input className="notes-input" value={versionNotes} onChange={(event) => setVersionNotes(event.target.value)} placeholder="Version notes (optional)" /><button className="button button-primary compact-button" onClick={() => void addVersion()} disabled={busy}>{busy ? <LoaderCircle className="spin" size={14} /> : <Plus size={14} />}Add version</button></div></div></section></div>
}

function AreaChartIcon() {
  return <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true"><path d="M3 22.5h22M5 19l5-5 4 3 8-9" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /><path d="M18 8h4v4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>
}

export default App
