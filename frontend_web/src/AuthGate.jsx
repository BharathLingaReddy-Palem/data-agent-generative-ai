import { createContext, useContext, useEffect, useState } from 'react';
import { ArrowRight, ArrowUpRight, Check, Database, Eye, EyeOff, Fingerprint, Layers3, LockKeyhole, ShieldCheck, Sparkles, UserRound } from 'lucide-react';
import { getAccount, login, logout, register, setToken } from './api';

import { ThemeToggle } from './components/Theme';

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export function Brand({ compact = false }) {
  return <div className="brand"><span className="brand-mark"><Layers3 size={23} strokeWidth={1.7} /></span>
    {!compact && <span><strong>DataAgent<span className="brand-dot">.</span></strong><small>YOUR DATA. A CLEARER PICTURE.</small></span>}
  </div>;
}

const PREVIEWS = [
  { title: 'Know what you’re working with.', description: 'See column types, missing values and outliers before taking the next step.', labels: ['Column types', 'Missing values', 'Distributions'], heights: [35, 54, 78, 65, 93, 73, 52, 39, 23] },
  { title: 'Find the story in the numbers.', description: 'Explore relationships and trends, then ask questions grounded in your dataset.', labels: ['Relationships', 'Trends', 'Ask your data'], heights: [24, 33, 28, 50, 45, 67, 61, 80, 94] },
  { title: 'Turn exploration into a next step.', description: 'Compare supervised models and export the findings you want to share.', labels: ['Compare models', 'Predict outcomes', 'Export reports'], heights: [63, 84, 72, 92, 68, 88, 77, 96, 85] },
];

function WorkspacePreview() {
  const [selected, setSelected] = useState(0);
  const preview = PREVIEWS[selected];
  return <div className="auth-preview">
    <div className="preview-topline"><span><span className="status-dot" /> THE WORKSPACE, AT A GLANCE</span><span className="preview-caption">Product preview</span></div>
    <div className="preview-tabs" role="tablist" aria-label="Explore the workflow">
      {['01 · Profile', '02 · Discover', '03 · Predict'].map((label, index) => <button key={label} id={`preview-tab-${index}`} type="button" role="tab" aria-selected={selected === index} aria-controls="workspace-preview" tabIndex={selected === index ? 0 : -1} onClick={() => setSelected(index)} onKeyDown={event => {
        if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
          event.preventDefault(); const next = event.key === 'Home' ? 0 : event.key === 'End' ? 2 : (index + (event.key === 'ArrowRight' ? 1 : 2)) % 3;
          setSelected(next); document.getElementById(`preview-tab-${next}`)?.focus();
        }
      }}>{label}</button>)}
    </div>
    <div id="workspace-preview" role="tabpanel" aria-labelledby={`preview-tab-${selected}`} className="preview-body">
      <div><h3>{preview.title}</h3><p>{preview.description}</p></div>
      <div className="preview-bars" aria-hidden="true">{preview.heights.map((height, index) => <span key={index} style={{ height: `${height}%`, transitionDelay: `${index * 25}ms` }} />)}</div>
    </div>
    <div className="preview-tags">{preview.labels.map(label => <span key={label}><Check size={12} />{label}</span>)}</div>
  </div>;
}

export default function AuthGate({children}) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [password, setPassword] = useState('');
  const [capsLock, setCapsLock] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    const signedOut = () => { setUser(null); setPassword(''); };
    window.addEventListener('ds_signed_out', signedOut);
    if (sessionStorage.getItem('ds_access_token')) {
      getAccount().then(u => {if (active) setUser(u);})
        .catch(err => {if (active) setError(err.message);}).finally(() => {if (active) setLoading(false);});
    } else setLoading(false);
    return () => {active = false; window.removeEventListener('ds_signed_out', signedOut);};
  }, [retry]);
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    const values = new FormData(event.currentTarget);
    try {
      const username = values.get('username'), password = values.get('password');
      if (creating) await register(username, password);
      const result = await login(username, password);
      setToken(result.access_token); setUser(result.user); setPassword('');
    } catch (err) {setError(err.message);} finally {setBusy(false);}
  }
  async function signOut() {
      try {await logout();} catch (err) {setError(`Signed out on this device. ${err.message}`);}
      finally {setToken(null); setUser(null); setPassword(''); setShowPassword(false);}
  }
  if (loading) return <main className="auth-loading"><Brand /><span className="spinner" /><p>Opening your workspace…</p></main>;
  if (user) return <AuthContext.Provider value={{user, signOut}}>{children}</AuthContext.Provider>;
  if (sessionStorage.getItem('ds_access_token')) return <main className="auth-loading"><Brand /><div className="card" style={{maxWidth:420,textAlign:'center'}}><h2>Connection interrupted</h2><p className="text-sm text-secondary mt-3">{error || 'Your account could not be checked. Your session is still saved.'}</p><button className="btn btn-primary mt-4" onClick={() => {setLoading(true);setError('');setRetry(value=>value+1);}}>Retry connection</button></div></main>;
  return <main className="auth-scene">
    <div className="ambient-orb orb-one" aria-hidden="true" /><div className="ambient-orb orb-two" aria-hidden="true" />
    <header className="auth-header"><Brand /><span className="auth-header-note"><ShieldCheck size={15} /> A workspace of your own <ThemeToggle /></span></header>
    <div className="auth-layout">
      <section className="auth-story" aria-label="About DataAgent">
        <span className="eyebrow"><span className="status-dot" /> FROM RAW DATA TO REAL UNDERSTANDING</span>
        <h1>A little less guesswork.<br /><span>A lot more insight.</span></h1>
        <p className="auth-lede">Give your data a place to make sense. Explore, ask questions and build models in one focused workspace.</p>
        <WorkspacePreview />
        <div className="auth-capabilities"><span><Database size={15} /> CSV & Excel</span><span><Sparkles size={15} /> AI-assisted analysis</span><span><ArrowUpRight size={15} /> Shareable reports</span></div>
      </section>
      <section className="auth-card" aria-labelledby="auth-title">
        <div className="auth-card-shine" aria-hidden="true" />
        <div className="auth-form-icon"><Fingerprint size={29} strokeWidth={1.4} /></div>
        <div className="auth-switch" role="group" aria-label="Account access">
          <button type="button" aria-pressed={!creating} disabled={busy} className={!creating ? 'selected' : ''} onClick={() => {setCreating(false);setError('');}}>Sign in</button>
          <button type="button" aria-pressed={creating} disabled={busy} className={creating ? 'selected' : ''} onClick={() => {setCreating(true);setError('');}}>Create account</button>
        </div>
        <h2 id="auth-title">{creating ? 'Make room for discovery.' : 'Welcome back.'}</h2>
        <p className="auth-card-description">{creating ? 'Create your account and start exploring your data.' : 'Your data, your discoveries. Pick up where you left off.'}</p>
        <form className="auth-form" onSubmit={submit} aria-busy={busy}>
          <div className="form-field"><label htmlFor="auth-username">Username</label><div className="field-wrap"><UserRound size={17} /><input id="auth-username" name="username" placeholder="Enter your username" required minLength={3} maxLength={64} autoComplete="username" disabled={busy} aria-describedby={creating ? 'username-help' : undefined} /></div>
            {creating && <small id="username-help">3–64 letters, numbers, dots, underscores or hyphens.</small>}</div>
          <div className="form-field"><label htmlFor="auth-password">Password</label><div className="field-wrap"><LockKeyhole size={17} /><input id="auth-password" name="password" placeholder={creating ? 'Create a password' : 'Enter your password'} type={showPassword ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)} onKeyUp={e => setCapsLock(e.getModifierState('CapsLock'))} required minLength={creating ? 12 : 1} maxLength={128} autoComplete={creating ? 'new-password' : 'current-password'} disabled={busy} aria-describedby={creating ? 'password-help' : undefined} />
            <button className="password-toggle" type="button" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button></div>
            {creating && <small id="password-help" className={password.length >= 12 ? 'requirement-met' : ''}><Check size={12} /> At least 12 characters {password.length >= 12 && '— ready'}</small>}
            {capsLock && <small className="caps-lock" role="status">Caps Lock is on.</small>}</div>
          {error && <div className="form-error" role="alert">{error}</div>}
          <button className="auth-submit" type="submit" disabled={busy}>{busy ? <><span className="spinner" /> {creating ? 'Creating your workspace…' : 'Signing you in…'}</> : <>{creating ? 'Create your workspace' : 'Enter your workspace'}<ArrowRight size={18} /></>}</button>
        </form>
        <div className="auth-privacy"><ShieldCheck size={16} /><span>Your datasets and analysis are tied to your account.</span></div>
      </section>
    </div>
    <footer className="auth-footer"><span>Built for the curious. Designed for clarity.</span><span>Explore. Understand. Decide.</span></footer>
  </main>;
}
