export function boxTraces(numericCols, columns) {
  return numericCols.slice(0,8).flatMap(name => {
    const box = columns[name]?.distribution?.box_summary;
    if (!box || !['q1','median','q3','lower_whisker','upper_whisker'].every(key => Number.isFinite(box[key]))) return [];
    return [{type:'box', name, x:[name], orientation:'v', q1:[box.q1], median:[box.median], q3:[box.q3],
      lowerfence:[box.lower_whisker], upperfence:[box.upper_whisker], boxpoints:false,
      marker:{color:'rgba(0, 180, 216, 0.7)'}, line:{color:'#00b4d8'}}];
  });
}

export function distributionTrace(distribution, name) {
  const histogram = distribution?.histogram;
  if (histogram?.bin_centers?.length && histogram.counts?.length === histogram.bin_centers.length) {
    return {type:'bar', x:histogram.bin_centers, y:histogram.counts, name,
      marker:{color:'rgba(0, 180, 216, 0.75)'}, hovertemplate:'Bin center: %{x}<br>Count: %{y}<extra></extra>'};
  }
  const points = Object.entries(distribution?.percentiles || {}).filter(([,value]) => Number.isFinite(value)).sort((a,b) => Number(a[0].slice(1))-Number(b[0].slice(1)));
  return {type:'scatter', mode:'lines+markers', name:'Quantile summary',
    x:points.map(([key]) => Number(key.slice(1))), y:points.map(([,value]) => value),
    hovertemplate:'Percentile: %{x}<br>Value: %{y}<extra></extra>'};
}
