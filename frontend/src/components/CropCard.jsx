import React from "react";

export default function CropCard({ data }) {
  return (
    <div className="card" style={{padding:"1rem"}}>
      <h4>{data.crop}</h4>
      <p>Score: <strong>{data.score}</strong> — {data.tag}</p>
      <p>Temp: {data.rule.temp_min}–{data.rule.temp_max}°C</p>
      <p>Rain: {data.rule.rain_min}–{data.rule.rain_max} mm</p>
    </div>
  );
}
