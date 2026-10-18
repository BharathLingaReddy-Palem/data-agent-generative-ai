import { UploadCloud, BarChart3, Activity, Brain, MessageSquare, FileText, Database, Cpu, ChevronRight, LogOut, X, Search, GitBranch, TrendingUp } from 'lucide-react';
import { useStore } from '../useStore';
import { Brand, useAuth } from '../AuthGate';

export const navItems = [
  { id: 'upload', label: 'Upload & Profile', icon: UploadCloud },
  { id: 'overview', label: 'Data Overview', icon: Database },
  { id: 'quality', label: 'Health & Quality', icon: Activity },
  { id: 'eda', label: 'EDA & Distributions', icon: BarChart3 },
  { id: 'clean', label: 'Clean Data', icon: Activity },
  { id: 'explorer', label: 'Data Explorer', icon: Search },
  { id: 'history', label: 'Version History', icon: GitBranch },
  { id: 'automl', label: 'Train & Compare', icon: Cpu, badge: 'ML', group:'Machine Learning' },
  { id: 'features', label: 'Feature Selection', icon: Activity },
  { id: 'forecast', label: 'Forecasting', icon: TrendingUp },
  { id: 'text', label: 'Text Classification', icon: MessageSquare },
  { id: 'runs', label: 'Saved Runs', icon: GitBranch },
  { id: 'batch', label: 'Batch Prediction', icon: Database },
  { id: 'insights', label: 'AI Insights', icon: Brain, badge: 'AI', group:'Insights & Reports' },
  { id: 'chat', label: 'Chat Analyst', icon: MessageSquare, badge: 'AI' },
  { id: 'builder', label: 'Report Builder', icon: FileText },
  { id: 'report', label: 'Executive Report', icon: FileText },
];

export default function Sidebar({ projectId, mobileOpen, onNavigate, onClose }) {
  const { state, actions } = useStore();
  const { user, signOut } = useAuth();
  return <aside className="sidebar" id="workspace-navigation" aria-label="Workspace navigation" onKeyDown={event => {
    if (!mobileOpen || event.key !== 'Tab') return;
    const buttons = [...event.currentTarget.querySelectorAll('button:not(:disabled)')];
    const first = buttons[0], last = buttons[buttons.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }}>
    <Brand />
    <button className="icon-button sidebar-close" aria-label="Close navigation" onClick={onClose}><X size={17} /></button>
    <nav aria-label="Analysis pages">
      <div className="nav-caption">Workspace</div>
      {navItems.map(item => {
        const Icon = item.icon, active = state.activeTab === item.id;
        const locked = !projectId && item.id !== 'upload';
        return <div key={item.id}>{item.group&&<div className="nav-caption">{item.group}</div>}<button className={`sidebar-nav-item ${active ? 'active' : ''}`} disabled={locked} aria-current={active ? 'page' : undefined} title={locked ? `${item.label} — load a dataset first` : item.label} onClick={() => { actions.setTab(item.id); onNavigate?.(); }}>
          <Icon size={17} className="icon" /><span className="nav-label">{item.label}</span>
          {item.badge && <span className="nav-badge">{item.badge}</span>}
          {active && <ChevronRight size={13} className="nav-chevron" />}
        </button></div>;
      })}
    </nav>
    <div className="sidebar-footer">
      <div className="dataset-status"><span><span className="status-dot" />{projectId ? 'Dataset connected' : 'Start with a dataset'}</span>
        <p>{projectId ? state.datasetName : 'Upload a file or explore a sample.'}</p>
        {projectId && state.profile && <p style={{ marginTop: 6 }}>{state.profile.overview?.total_rows?.toLocaleString()} rows · {state.profile.overview?.total_columns} columns</p>}
      </div>
      <div className="account-row"><span className="account-avatar" aria-hidden="true">{user.username.slice(0, 1).toUpperCase()}</span>
        <div className="account-info"><strong>{user.username}</strong><small>Personal workspace</small></div>
        <button className="icon-button" title="Sign out" aria-label={`Sign out (${user.username})`} onClick={signOut}><LogOut size={15} /></button>
      </div>
    </div>
  </aside>;
}
