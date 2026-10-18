// EDAPage.jsx — Exploratory Data Analysis with Plotly charts
import { useState } from 'react';
import { motion } from 'framer-motion';
import Plot from '../components/ThemedPlot';
import { BarChart3, TrendingUp, Grid, Sparkles } from 'lucide-react';
import { useStore } from '../useStore';
import { boxTraces, distributionTrace } from '../chartData';

const plotLayout = {
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  font: { family: 'Inter, sans-serif', color: '#a0a0a0', size: 11 },
  margin: { l: 40, r: 15, t: 20, b: 40 },
  showlegend: false,
};

function HistogramChart({ col, info }) {
  if (!info?.distribution) return null;
  const { mean, std, min, max, percentiles, histogram } = info.distribution;

  const trace = distributionTrace(info.distribution, col);
  const isHistogram = trace.type === 'bar';
  const plotData = [trace];
  const yMax = isHistogram ? Math.max(...trace.y, 1) : null;

  // Mean indicator line properly scaled to match data height
  if (isHistogram && mean !== undefined && mean !== null) {
    plotData.push({
      type: 'scatter',
      mode: 'lines',
      x: [mean, mean],
      y: [0, yMax * 1.15],
      line: { color: '#00ff88', dash: 'dot', width: 2 },
      name: 'Mean',
      hovertemplate: `Mean: ${mean?.toFixed(2)}<extra></extra>`,
    });
  }

  return (
    <Plot
      data={plotData}
      layout={{
        ...plotLayout,
        bargap: 0.08,
        xaxis: { title: {text:isHistogram ? 'Value' : 'Percentile'}, color:'#606060', gridcolor:'rgba(255,255,255,0.04)' },
        yaxis: { title: {text:isHistogram ? 'Count' : 'Value'}, color:'#606060', gridcolor:'rgba(255,255,255,0.04)', ...(isHistogram ? {range:[0,yMax*1.25]} : {}) },
        title: { text: col, font: { size: 11, color: '#a0a0a0' }, x: 0.05 },
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%', height: 180 }}
      useResizeHandler
    />
  );
}

function AIChartCard({ chart, index }) {
  let chartData = chart?.data || [];
  let chartLayout = chart?.layout || {};

  // If chart.data is empty, parse from chart.json or chart.spec
  if ((!chartData || chartData.length === 0) && chart?.json) {
    try {
      const parsed = typeof chart.json === 'string' ? JSON.parse(chart.json) : chart.json;
      chartData = parsed.data || [];
      chartLayout = parsed.layout || {};
    } catch (e) {
      console.warn("Failed to parse chart json:", e);
    }
  } else if ((!chartData || chartData.length === 0) && chart?.spec) {
    try {
      const parsed = typeof chart.spec === 'string' ? JSON.parse(chart.spec) : chart.spec;
      chartData = parsed.data || [];
      chartLayout = parsed.layout || {};
    } catch (e) {
      console.warn("Failed to parse chart spec:", e);
    }
  }

  const rawTitle = chart?.title || (typeof chartLayout?.title === 'string' ? chartLayout.title : chartLayout?.title?.text) || `Analysis Chart ${index + 1}`;
  const cleanTitle = String(rawTitle).replace(/^[📈📊📅🎯🌊📦🔥]\s*/, '');

  return (
    <div className="card" style={{ padding: 16 }}>
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-xs font-bold text-primary flex items-center gap-1.5" style={{ letterSpacing: '0.01em' }}>
          <Sparkles size={13} className="text-accent" />
          {cleanTitle}
        </h4>
        {chart?.type && (
          <span className="badge badge-blue" style={{ fontSize: '0.65rem', textTransform: 'capitalize' }}>
            {chart.type.replace(/_/g, ' ')}
          </span>
        )}
      </div>
      <Plot
        data={chartData}
        layout={{
          ...plotLayout,
          ...chartLayout,
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(0,0,0,0)',
          autosize: true,
          margin: { l: 50, r: 25, t: 25, b: 50 },
          font: { family: 'Inter, sans-serif', color: '#a0a0a0', size: 11 },
          title: undefined, // Rendered cleanly in header above
        }}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: '100%', height: 320 }}
        useResizeHandler
      />
    </div>
  );
}

function BoxPlotChart({ numericCols, colsData }) {
  const cols = numericCols.slice(0, 8);
  return (
    <Plot
      data={boxTraces(cols, colsData)}
      layout={{
        ...plotLayout,
        xaxis: { color: '#606060', tickangle: -20 },
        yaxis: { color: '#606060', gridcolor: 'rgba(255,255,255,0.04)' },
        margin: { l: 40, r: 10, t: 10, b: 60 },
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%', height: 260 }}
      useResizeHandler
    />
  );
}

export default function EDAPage() {
  const { state } = useStore();
  const { profile, analysis } = state;
  const [activeViz, setActiveViz] = useState('histograms');
  const [boxColumn, setBoxColumn] = useState('');

  const cols = profile?.columns || {};
  const numericCols = Object.entries(cols)
    .filter(([, v]) => v.col_type?.includes('numeric') && v.distribution)
    .map(([k]) => k);
  const catCols = Object.entries(cols)
    .filter(([, v]) => v.col_type?.includes('categorical') || v.col_type === 'boolean')
    .map(([k]) => k);

  const tabs = [
    { id: 'histograms', label: 'Distributions', icon: BarChart3 },
    { id: 'boxplots', label: 'Box Plots', icon: TrendingUp },
    { id: 'categories', label: 'Categories', icon: Grid },
  ];

  if (!profile) {
    return (
      <div className="flex items-center justify-center" style={{ height: '50vh', color: 'var(--text-tertiary)' }}>
        Upload a dataset first
      </div>
    );
  }

  return (
    <div>
      <motion.h2
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        style={{ fontSize: '1.4rem', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: 24 }}
      >
        Exploratory Data Analysis
      </motion.h2>

      <div className="tabs">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={`tab ${activeViz === id ? 'active' : ''}`}
            aria-pressed={activeViz === id}
            onClick={() => setActiveViz(id)}
            style={{ background: 'none', border: 'none', fontFamily: 'inherit', cursor: 'pointer' }}
          >
            <span className="flex items-center gap-2"><Icon size={14} />{label}</span>
          </button>
        ))}
      </div>

      <motion.div
        key={activeViz}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.2 }}
      >
        {activeViz === 'histograms' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 280px), 1fr))', gap: 16 }}>
            {numericCols.length > 0 ? numericCols.map((col) => (
              <div key={col} className="card" style={{ padding: 12 }}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-semibold text-primary truncate">{col}</span>
                  <span className="badge badge-blue" style={{ fontSize: '0.6rem' }}>
                    {cols[col]?.distribution?.distribution_shape?.split(' ')[0]}
                  </span>
                </div>
                <div className="flex gap-4 mb-2">
                  <span className="text-xs text-tertiary">μ={cols[col]?.distribution?.mean?.toFixed(2)}</span>
                  <span className="text-xs text-tertiary">σ={cols[col]?.distribution?.std?.toFixed(2)}</span>
                  <span className="text-xs text-tertiary">
                    skew={cols[col]?.distribution?.skewness?.toFixed(2)}
                  </span>
                </div>
                <HistogramChart col={col} info={cols[col]} />
              </div>
            )) : (
              <p className="text-secondary text-sm">No numeric columns found.</p>
            )}
          </div>
        )}

        {activeViz === 'boxplots' && (
          <div className="card">
            <div className="section-title">Box Plots — Numeric Columns</div>
            {numericCols.length > 0 ? (
              <><label className="text-sm text-secondary" htmlFor="box-column">Column to inspect</label><select id="box-column" style={{margin:'0 0 16px 12px'}} value={numericCols.includes(boxColumn) ? boxColumn : numericCols[0]} onChange={event=>setBoxColumn(event.target.value)}>{numericCols.map(col=><option key={col}>{col}</option>)}</select><p className="text-xs text-secondary mb-4">Quartiles and observed whiskers for one column. Different units are not mixed on a shared scale.</p><BoxPlotChart numericCols={[numericCols.includes(boxColumn) ? boxColumn : numericCols[0]]} colsData={cols} /></>
            ) : (
              <p className="text-secondary text-sm">No numeric columns with a box summary are available.</p>
            )}
          </div>
        )}

        {activeViz === 'categories' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 320px), 1fr))', gap: 16 }}>
            {catCols.length > 0 ? catCols.map((col) => {
              const vc = cols[col]?.value_counts || {};
              const entries = Object.entries(vc).slice(0, 10);
              if (entries.length === 0) return null;
              return (
                <div key={col} className="card">
                  <div className="text-sm font-semibold text-primary mb-3">{col}</div>
                  <Plot
                    data={[{
                      type: 'bar',
                      x: entries.map(([k]) => k),
                      y: entries.map(([, v]) => v),
                      marker: {
                        color: entries.map((_, i) => `hsl(${160 + i * 20}, 70%, 50%)`),
                        opacity: 0.8,
                      },
                      hovertemplate: '<b>%{x}</b><br>%{y} records<extra></extra>',
                    }]}
                    layout={{
                      ...plotLayout,
                      xaxis: { color: '#606060', tickangle: -20, tickfont: { size: 10 } },
                      yaxis: { color: '#606060', gridcolor: 'rgba(255,255,255,0.04)' },
                      margin: { l: 30, r: 10, t: 10, b: 60 },
                    }}
                    config={{ displayModeBar: false, responsive: true }}
                    style={{ width: '100%', height: 180 }}
                    useResizeHandler
                  />
                </div>
              );
            }) : (
              <p className="text-secondary text-sm">No categorical columns found.</p>
            )}
          </div>
        )}
      </motion.div>

      {/* Plotly charts from AI analysis */}
      {analysis?.charts?.length > 0 && (
        <div className="mt-8">
          <div className="section-title flex items-center gap-2 mb-4">
            <Sparkles size={16} className="text-accent" />
            AI-Generated Analytical Evidence Charts ({analysis.charts.length})
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 420px), 1fr))', gap: 16 }}>
            {analysis.charts.map((chart, i) => (
              <AIChartCard key={i} chart={chart} index={i} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
