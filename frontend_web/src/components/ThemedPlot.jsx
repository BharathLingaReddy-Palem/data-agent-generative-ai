import { useEffect, useRef, useState } from 'react';
import Plot from 'react-plotly.js';
import { useTheme } from './Theme';

export default function ThemedPlot({ layout = {}, data = [], style = {}, config = {}, ...props }) {
  const { theme } = useTheme();
  const wrapper = useRef(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const observer = new ResizeObserver(entries => setWidth(Math.round(entries[0].contentRect.width)));
    if (wrapper.current) observer.observe(wrapper.current);
    return () => observer.disconnect();
  }, []);
  const ink = theme === 'light' ? '#485970' : '#bdcadb';
  const grid = theme === 'light' ? '#253c5c13' : '#c2d9f015';
  const axis = value => ({ ...value, title: typeof value?.title === 'string' ? { text: value.title } : value?.title,
    color: ink, gridcolor: grid, zerolinecolor: grid, automargin: true,
    tickfont: { ...value?.tickfont, color: ink, size: Math.max(value?.tickfont?.size || 11, 11) } });
  const themedLayout = { ...layout, autosize: false, width: width || undefined,
    height: layout.height || (typeof style.height === 'number' ? style.height : 280),
    paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
    font: { family: '-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif', ...layout.font, color: ink, size: 12 },
    margin: { l: 50, r: 20, t: 30, b: 55, ...layout.margin },
    xaxis: axis(layout.xaxis), yaxis: axis(layout.yaxis),
    title: typeof layout.title === 'string' ? {text: layout.title, font: {color: ink}} : layout.title ? {...layout.title, font: {...layout.title.font, color: ink}} : undefined,
    legend: {...layout.legend, font: {color: ink}},
  };
  const themedData = data.map(trace => ({ ...trace,
    ...(trace.type === 'heatmap' ? { colorscale: [[0,'#536ad5'],[.5, theme === 'light' ? '#f3f6fb' : '#273347'],[1,'#16896c']], colorbar: {...trace.colorbar, tickfont:{color:ink,size:11}} } : {}),
    ...(trace.line?.color === '#00ff88' ? {line: {...trace.line, color: theme === 'light' ? '#16896c' : '#8ae8bf'}} : {}),
  }));
  for (const [key, value] of Object.entries(layout)) {
    if (/^[xy]axis\d*$/.test(key)) themedLayout[key] = axis(value);
  }
  return <div ref={wrapper} className="chart-container" style={{width:'100%',minWidth:0}}>
    <Plot {...props} data={themedData} layout={themedLayout} style={{...style,width:'100%'}} config={{...config,responsive:true,displaylogo:false}} />
  </div>;
}
