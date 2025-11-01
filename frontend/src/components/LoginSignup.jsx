import React, { useState } from "react";
import { api } from "../lib/api.js";

export default function LoginSignup(){
  const [user,setUser] = useState("");
  const [pass,setPass] = useState("");
  const [msg,setMsg] = useState("");

  async function doSignup(){
    try{
      const res = await api.signup(user, pass);
      localStorage.setItem("token", res.access_token);
      setMsg("Signed up");
    }catch(e){ setMsg(String(e.message||e)); }
  }
  async function doLogin(){
    try{
      const res = await api.login(user, pass);
      localStorage.setItem("token", res.access_token);
      setMsg("Logged in");
    }catch(e){ setMsg(String(e.message||e)); }
  }

  return (
    <section className="container">
      <h2>Login / Signup</h2>
      <div className="card">
        <input className="input" placeholder="username" value={user} onChange={e=>setUser(e.target.value)} />
        <input className="input" placeholder="password" value={pass} onChange={e=>setPass(e.target.value)} />
        <div style={{display:"flex",gap:8}}>
          <button className="btn" onClick={doLogin}>Login</button>
          <button className="btn" onClick={doSignup}>Signup</button>
        </div>
        {msg && <p style={{color:'#c00'}}>{msg}</p>}
      </div>
    </section>
  );
}
