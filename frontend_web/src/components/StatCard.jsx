// StatCard.jsx — Animated metric card with counter animation
import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

function useCountUp(target, duration = 1200) {
  const [count, setCount] = useState(0);
  const frameRef = useRef();
  const startRef = useRef();

  useEffect(() => {
    if (target === 0) { setCount(0); return; }
    startRef.current = performance.now();

    const step = (now) => {
      const elapsed = now - startRef.current;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setCount(Math.round(eased * target));
      if (progress < 1) frameRef.current = requestAnimationFrame(step);
    };

    frameRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frameRef.current);
  }, [target, duration]);

  return count;
}

export default function StatCard({
  label,
  value,
  unit = '',
  trend = null,      // 'up' | 'down' | null
  trendValue = null, // e.g. "+18%"
  color = 'default', // 'default' | 'accent' | 'warning' | 'danger'
  icon: Icon = null,
  animate = false,
  delay = 0,
  subtitle = null,
}) {
  const numericValue = typeof value === 'number' ? value : parseFloat(value) || 0;
  const isFloat = typeof value === 'number' && !Number.isInteger(value);

  const animated = useCountUp(animate ? numericValue : 0);
  const displayed = animate
    ? (isFloat ? animated.toFixed(1) : animated.toLocaleString())
    : (typeof value === 'number' ? value.toLocaleString() : value);

  const colorMap = {
    default: 'var(--text-primary)',
    accent: 'var(--accent-green)',
    warning: 'var(--accent-amber)',
    danger: 'var(--accent-red)',
    blue: 'var(--accent-blue)',
    purple: 'var(--accent-purple)',
  };

  return (
    <motion.div
      className="stat-card"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="stat-label">{label}</span>
        {Icon && (
          <div style={{
            width: 28, height: 28,
            borderRadius: 'var(--radius-sm)',
            background: 'rgba(255,255,255,0.04)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Icon size={14} style={{ color: colorMap[color] || colorMap.default }} />
          </div>
        )}
      </div>

      <div className="flex items-end gap-2">
        <span
          className="stat-value"
          style={{ color: colorMap[color] || colorMap.default }}
        >
          {displayed}
          {unit && <span style={{ fontSize: '0.55em', fontWeight: 600, marginLeft: 2, opacity: 0.7 }}>{unit}</span>}
        </span>
      </div>

      {(trend || subtitle) && (
        <div className="flex items-center gap-2 mt-2">
          {trend && (
            <div className={`stat-change ${trend === 'down' ? 'negative' : ''}`}>
              {trend === 'up' && <TrendingUp size={12} />}
              {trend === 'down' && <TrendingDown size={12} />}
              {trend === 'neutral' && <Minus size={12} />}
              {trendValue}
            </div>
          )}
          {subtitle && (
            <span className="text-xs text-tertiary">{subtitle}</span>
          )}
        </div>
      )}
    </motion.div>
  );
}
