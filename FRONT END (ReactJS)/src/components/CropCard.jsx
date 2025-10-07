import React from "react";

export default function CropCard({ data }) {
  const cls = data.tag === "Excellent" ? "badge good"
            : data.tag === "Good" ? "badge good"
            : data.tag === "Moderate" ? "badge ok" : "badge low";
  return (
    <article className="card">
      <h3 style={{margin:"0 0 .4rem"}}>{data.crop}</h3>
      <div className={cls}>{data.tag}</div>
      <p className="mt1" style={{color:"#555"}}>
        Score: <strong>{data.score}</strong><br/>
        Avg Temp: {data.avg_temp_c?.toFixed?.(1)}°C<br/>
        Rain (sum ~3d): {data.total_rain_mm?.toFixed?.(1)} mm
      </p>
      <p className="mt1" style={{fontSize:".9rem",color:"#666"}}>
        Rule: {data.rule.temp_min}–{data.rule.temp_max}°C, {data.rule.rain_min}–{data.rule.rain_max} mm
      </p>
    </article>
  );
}
