import {useState,useEffect} from 'react';
import {Sparkles} from 'lucide-react';
import {useStore} from '../useStore';
import {workspaceRequest as ws,restoreProject} from '../api';
export function useWorkspace() {
  const {state,actions}=useStore();const [data,setData]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const pid=state.projectId;
  useEffect(()=>{const controller=new AbortController();setData(null);ws(pid,'',undefined,controller.signal).then(setData).catch(e=>{if(!controller.signal.aborted)setError(e.message);});return()=>controller.abort();},[pid,state.profile]);
  async function refresh(){const next=await ws(pid);setData(next);return next;}
  async function change(path,payload){setBusy(true);setError('');try {const next=await ws(pid,path,payload);setData(next);const restored=await restoreProject(pid);actions.selectSavedProject(restored);actions.setTab(state.activeTab,pid);return next;}catch(e){setError(e.message);}finally{setBusy(false);}}
  return {state,actions,pid,data,setData,error,setError,busy,setBusy,refresh,change};
}
export function Heading({eyebrow='YOUR DATA WORKSPACE',title,children}) {return <header className="ws-heading"><span className="ws-eyebrow"><Sparkles size={13}/>{eyebrow}</span><h1>{title}</h1><p>{children}</p></header>;}
export function Notice({error,children}){return error?<p role="alert" className="ws-notice ws-error">{error}</p>:children?<p role="status" className="ws-notice">{children}</p>:null;}
export function Field({label,children}){return <label className="ws-field"><span>{label}</span>{children}</label>;}
export function Select({label,value,onChange,columns,empty='Choose a column'}){return <Field label={label}><select aria-label={label} value={value} onChange={e=>onChange(e.target.value)}><option value="">{empty}</option>{columns.map(c=><option key={c} value={c}>{c}</option>)}</select></Field>;}
export function Table({rows=[],columns,onSort,sort,descending}) {
  const cols=columns || Object.keys(rows[0]||{});
  return <div className="ws-table-wrap" tabIndex={0} aria-label="Scrollable data table"><table className="ws-table"><thead><tr>{cols.map(c=><th key={c} aria-sort={sort===c?(descending?'descending':'ascending'):undefined}>{onSort?<button onClick={()=>onSort(c)}>{c}{sort===c?(descending?' ↓':' ↑'):' ↕'}</button>:c}</th>)}</tr></thead><tbody>{rows.map((r,i)=><tr key={i}>{cols.map(c=><td key={c} title={r[c]==null?'Missing':String(r[c])}>{r[c]==null?<span className="ws-missing">Missing</span>:typeof r[c]==='object'?JSON.stringify(r[c]):String(r[c])}</td>)}</tr>)}</tbody></table>{!rows.length&&<p className="ws-empty">No rows match this selection.</p>}</div>;
}
export function Metrics({summary={}}){return <div className="ws-metrics">{[['Rows',typeof summary.rows==='number'?summary.rows:summary.filtered_rows],['Columns',summary.columns?.length ?? summary.columns],['Missing cells',summary.missing_cells],['Duplicates',summary.duplicates],['Quality score',summary.quality]].filter(([,v])=>v!==undefined).map(([k,v])=><div key={k}><span>{k}</span><strong>{typeof v==='number'?v.toLocaleString():v}</strong></div>)}</div>;}

