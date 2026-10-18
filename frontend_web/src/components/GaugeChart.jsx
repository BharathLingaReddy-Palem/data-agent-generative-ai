import { motion } from 'framer-motion';

export default function GaugeChart({ score = 0 }) {
  const value = Number.isFinite(Number(score)) ? Math.min(100, Math.max(0, Number(score))) : 0;
  const label = value >= 90 ? 'Excellent' : value >= 75 ? 'Good' : value >= 50 ? 'Fair' : 'Poor';
  const color = value >= 75 ? 'var(--accent-green)' : value >= 50 ? 'var(--accent-amber)' : 'var(--accent-red)';
  const arc = 'M 25 115 A 95 95 0 0 1 215 115';
  return <div className="gauge-container" role="img" aria-label={`Data quality ${Number(value.toFixed(1))} out of 100: ${label}`}>
    <svg viewBox="0 0 240 175" aria-hidden="true">
      <path d={arc} fill="none" stroke="var(--border-medium)" strokeWidth="12" strokeLinecap="round" />
      <motion.path d={arc} fill="none" stroke={color} strokeWidth="12" strokeLinecap="round" pathLength="100"
        initial={{strokeDasharray:'0 100'}} animate={{strokeDasharray:`${value} 100`}} transition={{duration:.65}} />
      <text x="120" y="105" textAnchor="middle" fill="var(--text-primary)" fontSize="42" fontWeight="600">{Number(value.toFixed(1))}</text>
      <text x="120" y="132" textAnchor="middle" fill={color} fontSize="14" fontWeight="600">{label}</text>
      <text x="25" y="143" textAnchor="middle" fill="var(--text-tertiary)" fontSize="11">0</text>
      <text x="215" y="143" textAnchor="middle" fill="var(--text-tertiary)" fontSize="11">100</text>
    </svg>
  </div>;
}
