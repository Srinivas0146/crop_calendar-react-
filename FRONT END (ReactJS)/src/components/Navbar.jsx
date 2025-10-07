import React from "react";
import { Link, useNavigate } from "react-router-dom";

export default function Navbar() {
  const navigate = useNavigate();
  const token = localStorage.getItem("token");

  function logout() {
    localStorage.removeItem("token");
    navigate("/");
  }

  return (
    <nav className="container" style={{display:"flex",gap:"1rem",alignItems:"center",borderBottom:"1px solid #eee",padding:"0.75rem 0"}}>
      <strong style={{fontSize:"1.15rem"}}>CropWise</strong>
      <Link to="/">Home</Link>
      <Link to="/about">About</Link>
      <Link to="/contact">Contact</Link>
      <Link to="/calendar">Calendar</Link>
      <span style={{marginLeft:"auto"}}>
        {token ? <button className="btn" onClick={logout}>Logout</button>
               : <Link className="btn" to="/auth">Login / Signup</Link>}
      </span>
    </nav>
  );
}
