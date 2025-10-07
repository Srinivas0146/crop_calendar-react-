import React, { useEffect, useState } from "react";
import { api } from "../lib/api.js";
import CropCard from "./CropCard.jsx";

export default function Calendar() {
  const [recentPlaces, setRecentPlaces] = useState([]);
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState([]);
  const [selectedPlace, setSelectedPlace] = useState("");
  const [season, setSeason] = useState("");
  const [live, setLive] = useState(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api.states().then(setRecentPlaces).catch(()=>{});
    api.logEvent("open_calendar", {});
  }, []);

  // Whenever the user changes place or season, clear previous results + message
  useEffect(() => {
    setLive(null);
    setMsg("");
  }, [selectedPlace, season]);

  async function searchPlaces(q) {
    setQuery(q);
    if (q.trim().length < 2) { setMatches([]); return; }
    try {
      const res = await api.geocode(q.trim());
      setMatches(res);
    } catch (e) {
      setMatches([]);
      setMsg(String(e.message || e));
    }
  }

  async function autoSeason() {
    if (!selectedPlace) return setMsg("Select a place first.");
    setMsg(""); setLoading(true); setLive(null);
    try {
      const s = await api.seasonNow(selectedPlace);
      setSeason(s.season);
      await api.logEvent("auto_season", { place: selectedPlace, season: s.season });
    } catch (e) {
      setMsg(`Auto-detect failed: ${e.message || e}`);
    } finally { setLoading(false); }
  }

  async function fetchLive() {
    if (!selectedPlace) return setMsg("Select a place first.");
    if (!season) return setMsg("Choose a season or use Auto-detect.");
    setMsg(""); setLoading(true); setLive(null);
    try {
      const res = await api.liveCrops(selectedPlace, season);
      setLive(res);
      await api.logEvent("live_crops", { place: selectedPlace, season });
    } catch (e) {
      setMsg(`Live crops failed: ${e.message || e}`);
    } finally { setLoading(false); }
  }

  return (
    <section className="container">
      <h2>Crop Calendar</h2>

      <div className="card mt1">
        <div className="row">
          <div style={{minWidth:320, flex:1}}>
            <label>Search Place (State/UT/District/City)</label>
            <input className="input mt1" value={query}
                   onChange={e=>searchPlaces(e.target.value)}
                   placeholder="e.g., Guntur, Andhra Pradesh"/>
            {matches.length>0 && (
              <div className="card mt1" style={{maxHeight:240, overflowY:"auto"}}>
                {matches.map((m,i)=>(
                  <div key={i} style={{padding:".4rem 0", cursor:"pointer"}}
                       onClick={()=>{ setSelectedPlace(m.name); setQuery(m.name); setMatches([]); }}>
                    {m.name} <span style={{color:"#777"}}>({m.lat.toFixed(2)}, {m.lon.toFixed(2)})</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div style={{minWidth:260}}>
            <label>Recent Places</label>
            <select className="select mt1" onChange={e=>setSelectedPlace(e.target.value)} value={selectedPlace}>
              <option value="">-- choose --</option>
              {recentPlaces.map(p => <option key={p.name} value={p.name}>{p.name}</option>)}
            </select>
          </div>
        </div>

        <div className="row mt1">
          <button className="btn" onClick={()=>setSeason("Kharif")}>Kharif</button>
          <button className="btn" onClick={()=>setSeason("Rabi")}>Rabi</button>
          <button className="btn" onClick={()=>setSeason("Summer")}>Summer</button>
          <button className="btn" onClick={autoSeason}>Auto-detect</button>
          <button className="btn" onClick={fetchLive}>View Live Crops</button>
        </div>

        {selectedPlace && <p className="mt1">Selected place: <span className="badge">{selectedPlace}</span></p>}
        {season && <p className="mt1">Selected season: <span className="badge">{season}</span></p>}
        {msg && <p className="mt1" style={{color:"#c00"}}>{msg}</p>}
      </div>

      {loading && <p className="mt2">Loading live weather & forecast…</p>}

      {live && (
        <div className="mt2">
          <h3>Live metrics for {live.state} ({live.season})</h3>
          <p className="mt1">Avg Temp: <strong>{live.metrics.avg_temp_c?.toFixed?.(1)}°C</strong>,
             Total Rain: <strong>{live.metrics.total_rain_mm?.toFixed?.(1)} mm</strong></p>
          <div className="grid mt2">
            {live.crops.map(c => <CropCard key={c.crop} data={c} />)}
          </div>
        </div>
      )}
    </section>
  );
}
