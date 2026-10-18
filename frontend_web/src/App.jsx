import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence, MotionConfig } from 'framer-motion';
import { StoreProvider, useStore } from './useStore';
import Sidebar, { navItems } from './components/Sidebar';
import AuthGate from './AuthGate';
import WorkflowGuide from './components/WorkflowGuide';
import { ThemeProvider, ThemeToggle } from './components/Theme';
import { ChevronRight, Search, PanelLeftClose, PanelLeftOpen, Menu, X } from 'lucide-react';

const PAGES = {
  features: lazy(() => import('./pages/AdvancedPages.jsx').then(m=>({default:m.FeatureSelectionPage}))),
  batch: lazy(() => import('./pages/AdvancedPages.jsx').then(m=>({default:m.BatchPredictionPage}))),
  clean: lazy(() => import('./pages/WorkspacePages.jsx').then(m => ({default:m.CleaningPage}))),
  explorer: lazy(() => import('./pages/WorkspacePages.jsx').then(m => ({default:m.ExplorerPage}))),
  history: lazy(() => import('./pages/WorkspacePages.jsx').then(m => ({default:m.HistoryPage}))),
  forecast: lazy(() => import('./pages/WorkspacePages.jsx').then(m => ({default:m.ForecastPage}))),
  text: lazy(() => import('./pages/WorkspacePages.jsx').then(m => ({default:m.TextPage}))),
  runs: lazy(() => import('./pages/WorkspacePages.jsx').then(m => ({default:m.SavedRunsPage}))),
  builder: lazy(() => import('./pages/WorkspacePages.jsx').then(m => ({default:m.ReportBuilderPage}))),

  upload: lazy(() => import('./pages/UploadPage.jsx')),
  overview: lazy(() => import('./pages/OverviewPage.jsx')),
  quality: lazy(() => import('./pages/QualityPage.jsx')),
  eda: lazy(() => import('./pages/EDAPage.jsx')),
  automl: lazy(() => import('./pages/AutoMLPage.jsx')),
  insights: lazy(() => import('./pages/InsightsPage.jsx')),
  chat: lazy(() => import('./pages/ChatPage.jsx')),
  report: lazy(() => import('./pages/ReportPage.jsx')),
};
const BREADCRUMBS = {features:['Machine Learning','Feature Selection'],batch:['Machine Learning','Batch Prediction'], clean:['Workspace','Clean Data'],explorer:['Workspace','Data Explorer'],history:['Workspace','Version History'],forecast:['Machine Learning','Forecasting'],text:['Machine Learning','Text Classification'],runs:['Machine Learning','Saved Runs'],builder:['Reports','Report Builder'], upload: ['Workspace', 'Upload & Profile'], overview: ['Analysis', 'Data Overview'], quality: ['Analysis', 'Health & Quality'], eda: ['Analysis', 'EDA & Distributions'], automl: ['Machine Learning', 'Train & Compare'], insights: ['Analysis', 'AI Insights'], chat: ['Workspace', 'Chat Analyst'], report: ['Analysis', 'Executive Report'] };

function PageSearch({ dialogRef }) {
  const { state, actions } = useStore();
  const [query, setQuery] = useState('');
  const results = navItems.filter(item => item.label.toLowerCase().includes(query.toLowerCase()));
  return <dialog ref={dialogRef} className="command-dialog" aria-labelledby="page-search-title" onClose={() => setQuery('')} onClick={event => { if (event.target === event.currentTarget) dialogRef.current.close(); }}>
    <header><h2 id="page-search-title">Where would you like to go?</h2><button className="icon-button" aria-label="Close page search" onClick={() => dialogRef.current.close()}><X size={16} /></button></header>
    <input className="input" type="search" aria-label="Find a page" placeholder="Search your workspace…" value={query} onChange={event => setQuery(event.target.value)} />
    <div className="command-results">{results.map(item => <button key={item.id} disabled={!state.projectId && item.id !== 'upload'} onClick={() => { actions.setTab(item.id); dialogRef.current.close(); }}><span>{item.label}</span>{!state.projectId && item.id !== 'upload' ? <small>Load a dataset first</small> : <ChevronRight size={15} />}</button>)}
      {!results.length && <p className="command-hint">No pages match “{query}”. Try “chat” or “quality”.</p>}</div>
    <p className="command-hint">Use Tab to move between results · Escape to close</p>
  </dialog>;
}

function AppInner() {
  const { state, actions } = useStore();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const searchRef = useRef(null), menuRef = useRef(null);
  const crumbs = BREADCRUMBS[state.activeTab] || [];
  const ActivePage = PAGES[state.activeTab] || PAGES.upload;
  useEffect(() => { document.getElementById('main-content')?.scrollTo({top:0, behavior:'instant'}); }, [state.activeTab]);
  function openSearch() {
    searchRef.current?.showModal();
    searchRef.current?.querySelector('input')?.focus();
  }
  function closeNavigation() { setMobileOpen(false); menuRef.current?.focus(); }
  function openNavigation() {
    setMobileOpen(true);
  }
  useEffect(() => {
    if (!mobileOpen) return;
    const frame = requestAnimationFrame(() => document.querySelector('.sidebar-close')?.focus());
    return () => cancelAnimationFrame(frame);
  }, [mobileOpen]);
  useEffect(() => {
    function shortcuts(event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); openSearch(); }
      if (event.key === 'Escape' && !searchRef.current?.open && document.querySelector('.mobile-nav-open')) closeNavigation();
    }
    window.addEventListener('keydown', shortcuts);
    return () => window.removeEventListener('keydown', shortcuts);
  }, []);
  useEffect(() => {
    const viewport = window.matchMedia('(max-width: 900px)');
    const resetMenu = () => { if (!viewport.matches) setMobileOpen(false); };
    viewport.addEventListener('change', resetMenu);
    return () => viewport.removeEventListener('change', resetMenu);
  }, []);
  return <div className={`dashboard-layout ${collapsed ? 'workspace-collapsed' : ''} ${mobileOpen ? 'mobile-nav-open' : ''}`}>
    <button className="nav-scrim" aria-label="Close navigation overlay" onClick={closeNavigation} />
    <Sidebar projectId={state.projectId} mobileOpen={mobileOpen} onNavigate={() => { setMobileOpen(false); document.getElementById('main-content')?.focus(); }} onClose={closeNavigation} />
    <header className="topbar" inert={mobileOpen}>
      <div className="topbar-left">
        <button className="icon-button desktop-collapse" aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} aria-expanded={!collapsed} aria-controls="workspace-navigation" onClick={() => setCollapsed(!collapsed)}>{collapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}</button>
        <button ref={menuRef} className="icon-button mobile-menu-button" aria-label="Open navigation" aria-expanded={mobileOpen} aria-controls="workspace-navigation" onClick={openNavigation}><Menu size={18} /></button>
        <div className="breadcrumb-stack"><div className="breadcrumb" aria-label="Current page">{crumbs.map((crumb, index) => <span key={crumb}>{index > 0 && <ChevronRight size={12} />}{crumb}</span>)}</div>{state.projectId&&<small className="persistent-version" aria-label="Active dataset version" title={state.workflowMeta?.version_label}>{state.workflowMeta?`Version ${state.workflowMeta.version_number} · ${state.workflowMeta.version_label}`:'Loading version…'}</small>}</div>
      </div>
      <div className="topbar-right"><ThemeToggle />{state.datasetName && <div className="dataset-pill"><span className="status-dot" /><span>{state.datasetName}</span></div>}
        <button className="command-trigger" aria-label="Search pages" onClick={openSearch}><Search size={15} /><span>Jump to a page</span><kbd>⌘ / Ctrl K</kbd></button>
      </div>
    </header>
    <main className="main-content" id="main-content" tabIndex={-1} inert={mobileOpen}>
      <WorkflowGuide/>
      <motion.div key={state.activeTab} initial={{ opacity: 0, y: 7 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} transition={{ duration: .18 }}><Suspense fallback={<div className="workspace-loading" role="status"><span className="spinner" /> Opening your page…</div>}><ActivePage key={state.projectId} /></Suspense></motion.div>
      {state.error && <div role="alert" className="form-error page-error" style={{ position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)', zIndex: 150, maxWidth: 'min(480px, calc(100vw - 32px))', background: '#291e25f5', boxShadow: 'var(--shadow-card)' }}><span>{state.error}</span><button className="icon-button" aria-label="Dismiss error" onClick={() => actions.setError(null)}><X size={15} /></button></div>}
    </main>
    <PageSearch dialogRef={searchRef} />
  </div>;
}

export default function App() {
  return <ThemeProvider><MotionConfig reducedMotion="user"><AuthGate><StoreProvider><AppInner /></StoreProvider></AuthGate></MotionConfig></ThemeProvider>;
}
