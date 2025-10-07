import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";

export default function LoginSignup() {
  const [tab, setTab] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState("");
  const navigate = useNavigate();

  async function doAuth(kind) {
    try {
      setMsg("");
      const res = kind === "login" ? await api.login(username, password)
                                   : await api.signup(username, password);
      localStorage.setItem("token", res.access_token);
      await api.logEvent(kind, { username });
      navigate("/calendar");
    } catch (e) { setMsg(String(e)); }
  }

  return (
    <section className="container">
      <div className="row mt2">
        <button className="btn" onClick={()=>setTab("login")} style={{background: tab==="login"?"#eef5ff":""}}>Login</button>
        <button className="btn" onClick={()=>setTab("signup")} style={{background: tab==="signup"?"#eef5ff":""}}>Signup</button>
      </div>

      <div className="card mt2" style={{maxWidth:480}}>
        <label>Username</label>
        <input className="input mt1" value={username} onChange={e=>setUsername(e.target.value)} placeholder="enter username"/>
        <label className="mt1">Password</label>
        <input className="input mt1" type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="enter password"/>

        <div className="row mt2">
          {tab==="login" ? <button className="btn" onClick={()=>doAuth("login")}>Login</button>
                         : <button className="btn" onClick={()=>doAuth("signup")}>Create Account</button>}
        </div>

        {msg && <p className="mt1" style={{color:"#c00"}}>{msg}</p>}
      </div>
    </section>
  );
}
