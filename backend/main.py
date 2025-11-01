from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from urllib.parse import quote

import requests
from fastapi import FastAPI, Depends, HTTPException, status, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, Session, create_engine, select

APP_TITLE = "CropWise – Real-Time Crop Calendar & Guidance System"
SECRET_KEY = os.getenv("CROPWISE_SECRET", "dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

DB_PATH = "auth_analytics.db"
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ---------------------------
# DB Models
# ---------------------------
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    is_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AnalyticsEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    event_name: str = Field(index=True)
    meta_json: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PlaceCache(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)  # e.g., "Guntur, Andhra Pradesh, IN"
    lat: float
    lon: float
    hits: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CropRule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    seasons_csv: str  # "Kharif,Rabi"
    temp_min: float
    temp_max: float
    rain_min: float
    rain_max: float
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------
# Schemas
# ---------------------------
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str
    password: str


class EventIn(BaseModel):
    event_name: str
    meta: Optional[dict] = None


class CropRuleIn(BaseModel):
    name: str
    seasons: List[str]
    temp_min: float
    temp_max: float
    rain_min: float
    rain_max: float
    active: bool = True


class CropRuleOut(BaseModel):
    id: int
    name: str
    seasons: List[str]
    temp_min: float
    temp_max: float
    rain_min: float
    rain_max: float
    active: bool
    created_at: datetime


# ---------------------------
# Startup & Auth helpers
# ---------------------------
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_user_by_username(session: Session, username: str) -> Optional[User]:
    return session.exec(select(User).where(User.username == username)).first()


def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    with Session(engine) as session:
        user = get_user_by_username(session, username)
        if user is None:
            raise credentials_exception
        return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ---------------------------
# External API helpers
# ---------------------------
def _get_json(url: str, timeout: int = 20) -> dict:
    """Requests wrapper with timeouts and clear error surfacing."""
    try:
        r = requests.get(url, timeout=timeout)
    except requests.RequestException as e:
        raise HTTPException(502, f"Upstream request failed: {e}")
    if r.status_code != 200:
        # Bubble up any upstream message (OpenWeather sends JSON or text)
        raise HTTPException(502, f"Upstream error {r.status_code}: {r.text}")
    try:
        return r.json()
    except ValueError:
        raise HTTPException(502, "Upstream returned non-JSON response")


def ow_geocode(query: str, limit: int = 5) -> List[dict]:
    if not OPENWEATHER_API_KEY:
        raise HTTPException(500, "OPENWEATHER_API_KEY not set on server")
    # Bias to India if user didn't specify a country already
    q = query.strip()
    if ",IN" not in q.upper() and ", INDIA" not in q.upper():
        q = f"{q}, IN"
    url = (
        "http://api.openweathermap.org/geo/1.0/direct"
        f"?q={quote(q)}&limit={limit}&appid={OPENWEATHER_API_KEY}"
    )
    return _get_json(url)


def ow_forecast(lat: float, lon: float) -> dict:
    if not OPENWEATHER_API_KEY:
        raise HTTPException(500, "OPENWEATHER_API_KEY not set on server")
    url = (
        "https://api.openweathermap.org/data/2.5/forecast"
        f"?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
    )
    return _get_json(url)


def forecast_summary(forecast_json: dict) -> dict:
    items = forecast_json.get("list", [])[:24]  # next ~72h
    if not items:
        return {"avg_temp_c": None, "total_rain_mm": None}
    temps = [x.get("main", {}).get("temp") for x in items]
    temps = [t for t in temps if isinstance(t, (int, float))]
    rain = 0.0
    for x in items:
        r3 = x.get("rain", {}).get("3h")
        rain += float(r3) if isinstance(r3, (int, float)) else 0.0
    avg_temp = sum(temps) / len(temps) if temps else None
    return {"avg_temp_c": avg_temp, "total_rain_mm": rain}


# ---------------------------
# Season logic (dynamic)
# ---------------------------
def month_to_season_base(month: int) -> str:
    if month in (6, 7, 8, 9, 10):
        return "Kharif"
    if month in (11, 12, 1, 2, 3):
        return "Rabi"
    return "Summer"  # Apr–May


def dynamic_season(month: int, avg_temp: Optional[float], total_rain: Optional[float]) -> str:
    """Bias season by weather signals."""
    base = month_to_season_base(month)
    if avg_temp is None or total_rain is None:
        return base
    if total_rain >= 40 and avg_temp >= 22:
        return "Kharif"
    if 10 <= avg_temp <= 25 and total_rain <= 30:
        return "Rabi"
    if avg_temp >= 30 and total_rain <= 20:
        return "Summer"
    return base


# ---------------------------
# Crop scoring
# ---------------------------
def score_crop(rule: CropRule, avg_temp: Optional[float], total_rain: Optional[float]) -> float:
    if avg_temp is None or total_rain is None:
        return 0.0
    tmin, tmax = rule.temp_min, rule.temp_max
    rmin, rmax = rule.rain_min, rule.rain_max
    # Temperature score
    if avg_temp < tmin:
        tscore = max(0.0, 100 - (tmin - avg_temp) * 8)
    elif avg_temp > tmax:
        tscore = max(0.0, 100 - (avg_temp - tmax) * 8)
    else:
        tscore = 100.0
    # Rainfall score
    if total_rain < rmin:
        rscore = max(0.0, 100 - (rmin - total_rain) * 2)
    elif total_rain > rmax:
        rscore = max(0.0, 100 - (total_rain - rmax) * 1.2)
    else:
        rscore = 100.0
    return round((tscore * 0.6 + rscore * 0.4), 2)


def tag_for_score(score: float) -> str:
    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Good"
    if score >= 40:
        return "Moderate"
    return "Low"


# ---------------------------
# App
# ---------------------------
app = FastAPI(title=APP_TITLE)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    # Seed default crop rules once (if empty)
    with Session(engine) as session:
        any_rule = session.exec(select(CropRule)).first()
        if not any_rule:
            defaults = [
                {"name": "Rice", "seasons": ["Kharif"], "temp_min": 20, "temp_max": 35, "rain_min": 50, "rain_max": 300},
                {"name": "Wheat", "seasons": ["Rabi"], "temp_min": 10, "temp_max": 25, "rain_min": 20, "rain_max": 100},
                {"name": "Maize", "seasons": ["Kharif", "Rabi"], "temp_min": 18, "temp_max": 32, "rain_min": 25, "rain_max": 150},
                {"name": "Pulses", "seasons": ["Rabi", "Kharif"], "temp_min": 18, "temp_max": 30, "rain_min": 20, "rain_max": 120},
                {"name": "Cotton", "seasons": ["Kharif"], "temp_min": 21, "temp_max": 30, "rain_min": 50, "rain_max": 150},
                {"name": "Groundnut", "seasons": ["Kharif", "Summer"], "temp_min": 20, "temp_max": 30, "rain_min": 25, "rain_max": 100},
                {"name": "Sorghum", "seasons": ["Kharif", "Rabi", "Summer"], "temp_min": 18, "temp_max": 32, "rain_min": 10, "rain_max": 100},
            ]
            for d in defaults:
                session.add(
                    CropRule(
                        name=d["name"],
                        seasons_csv=",".join(d["seasons"]),
                        temp_min=d["temp_min"],
                        temp_max=d["temp_max"],
                        rain_min=d["rain_min"],
                        rain_max=d["rain_max"],
                        active=True,
                    )
                )
            session.commit()


# ---------------------------
# Health
# ---------------------------
@app.get("/", tags=["health"])
def health():
    return {"status": "ok", "service": "CropWise API (dynamic)"}


# ---------------------------
# Auth
# ---------------------------
@app.post("/auth/signup", response_model=Token, tags=["auth"])
def signup(data: UserCreate):
    with Session(engine) as session:
        if get_user_by_username(session, data.username):
            raise HTTPException(400, "Username already exists")
        user = User(username=data.username, hashed_password=hash_password(data.password))
        # make first user or 'admin' an admin
        first_user = session.exec(select(User)).first()
        if first_user is None or data.username.lower() == "admin":
            user.is_admin = True
        session.add(user)
        session.commit()
        token = create_access_token({"sub": user.username})
        return {"access_token": token, "token_type": "bearer"}


@app.post("/auth/login", response_model=Token, tags=["auth"])
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    with Session(engine) as session:
        user = get_user_by_username(session, form_data.username)
        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(401, "Invalid credentials")
        token = create_access_token({"sub": user.username})
        return {"access_token": token, "token_type": "bearer"}


@app.get("/me", tags=["auth"])
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "is_admin": user.is_admin}


# ---------------------------
# Analytics (optional auth)
# ---------------------------
@app.post("/analytics/event", tags=["analytics"])
def log_event(event: EventIn, request: Request):
    # Try to resolve user from bearer token if present
    user_id = None
    try:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth.replace("Bearer ", "")
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        else:
            payload = None
        username = (payload or {}).get("sub")
        if username:
            with Session(engine) as session:
                u = get_user_by_username(session, username)
                if u:
                    user_id = u.id
    except Exception:
        pass

    with Session(engine) as session:
        rec = AnalyticsEvent(user_id=user_id, event_name=event.event_name, meta_json=str(event.meta) if event.meta else None)
        session.add(rec)
        session.commit()
        session.refresh(rec)
        return {"ok": True, "id": rec.id}


# ---------------------------
# Admin: crop rules CRUD
# ---------------------------
def _rule_to_out(r: CropRule) -> Dict[str, Any]:
    return {
        "id": r.id,
        "name": r.name,
        "seasons": [s for s in r.seasons_csv.split(",") if s],
        "temp_min": r.temp_min,
        "temp_max": r.temp_max,
        "rain_min": r.rain_min,
        "rain_max": r.rain_max,
        "active": r.active,
        "created_at": r.created_at,
    }


@app.get("/admin/crop_rules", response_model=List[CropRuleOut], tags=["admin"])
def list_rules(_: User = Depends(require_admin)):
    with Session(engine) as session:
        rs = session.exec(select(CropRule)).all()
    return [_rule_to_out(r) for r in rs]


@app.post("/admin/crop_rules", response_model=CropRuleOut, tags=["admin"])
def create_rule(data: CropRuleIn, _: User = Depends(require_admin)):
    with Session(engine) as session:
        r = CropRule(
            name=data.name,
            seasons_csv=",".join(data.seasons),
            temp_min=data.temp_min,
            temp_max=data.temp_max,
            rain_min=data.rain_min,
            rain_max=data.rain_max,
            active=data.active,
        )
        session.add(r)
        session.commit()
        session.refresh(r)
        return _rule_to_out(r)


@app.put("/admin/crop_rules/{rule_id}", response_model=CropRuleOut, tags=["admin"])
def update_rule(rule_id: int, data: CropRuleIn, _: User = Depends(require_admin)):
    with Session(engine) as session:
        r = session.get(CropRule, rule_id)
        if not r:
            raise HTTPException(404, "Rule not found")
        r.name = data.name
        r.seasons_csv = ",".join(data.seasons)
        r.temp_min, r.temp_max = data.temp_min, data.temp_max
        r.rain_min, r.rain_max = data.rain_min, data.rain_max
        r.active = data.active
        session.add(r)
        session.commit()
        session.refresh(r)
        return _rule_to_out(r)


@app.delete("/admin/crop_rules/{rule_id}", tags=["admin"])
def delete_rule(rule_id: int, _: User = Depends(require_admin)):
    with Session(engine) as session:
        r = session.get(CropRule, rule_id)
        if not r:
            raise HTTPException(404, "Rule not found")
        session.delete(r)
        session.commit()
        return {"ok": True}


# ---------------------------
# Places (dynamic)
# ---------------------------
@app.get("/geocode", tags=["data"])
def geocode(query: str = Query(..., description="Place name, e.g., 'Guntur' or 'Guntur, AP'")):
    results = ow_geocode(query, limit=5)
    out = []
    for x in results:
        bits = [x.get("name")]
        if x.get("state"):
            bits.append(x["state"])
        if x.get("country"):
            bits.append(x["country"])
        out.append({"name": ", ".join([b for b in bits if b]), "lat": x["lat"], "lon": x["lon"]})
    return out


@app.get("/states", tags=["data"])
def list_cached_places():
    with Session(engine) as session:
        places = session.exec(select(PlaceCache).order_by(PlaceCache.hits.desc(), PlaceCache.id.desc())).all()
        return [{"name": p.name, "lat": p.lat, "lon": p.lon, "hits": p.hits} for p in places]


def get_or_cache_place(session: Session, place: str) -> PlaceCache:
    # Check cache
    p = session.exec(select(PlaceCache).where(PlaceCache.name == place)).first()
    if p:
        p.hits += 1
        session.add(p)
        session.commit()
        session.refresh(p)
        return p

    # Not cached; geocode with India bias and prefer exact city match
    results = ow_geocode(place, limit=5)
    if not results:
        raise HTTPException(404, "Place not found")

    needle = place.split(",")[0].strip().lower()
    best = None
    for x in results:
        if x.get("name", "").strip().lower() == needle:
            best = x
            break
    if not best:
        best = results[0]

    bits = [best.get("name")]
    if best.get("state"):
        bits.append(best["state"])
    if best.get("country"):
        bits.append(best["country"])
    display = ", ".join([b for b in bits if b])

    p = PlaceCache(name=display, lat=best["lat"], lon=best["lon"], hits=1)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


# ---------------------------
# Season now (dynamic by weather)
# ---------------------------
@app.get("/season_now", tags=["data"])
def season_now(state: str = Query(..., description="Any place; geocoded live")):
    with Session(engine) as session:
        place = get_or_cache_place(session, state)
        fc = ow_forecast(place.lat, place.lon)
        summ = forecast_summary(fc)
        month = datetime.now().month
        season = dynamic_season(month, summ["avg_temp_c"], summ["total_rain_mm"])
        return {
            "state": place.name,
            "lat": place.lat,
            "lon": place.lon,
            "month": month,
            "season": season,
            "metrics": summ,
        }


# ---------------------------
# Live crops (uses DB crop rules)
# ---------------------------
@app.get("/live_crops", tags=["data"])
def live_crops(state: str, season: Optional[str] = None):
    with Session(engine) as session:
        place = get_or_cache_place(session, state)
        fc = ow_forecast(place.lat, place.lon)
        summ = forecast_summary(fc)

        if season is None:
            season = dynamic_season(datetime.now().month, summ["avg_temp_c"], summ["total_rain_mm"])

        rules = session.exec(select(CropRule).where(CropRule.active == True)).all()
        crops = []
        for r in rules:
            seasons = [s.strip() for s in r.seasons_csv.split(",") if s.strip()]
            if season not in seasons:
                continue
            sc = score_crop(r, summ["avg_temp_c"], summ["total_rain_mm"])
            crops.append(
                {
                    "crop": r.name,
                    "season": season,
                    "avg_temp_c": round(summ["avg_temp_c"], 2) if isinstance(summ["avg_temp_c"], (int, float)) else None,
                    "total_rain_mm": round(summ["total_rain_mm"], 2) if isinstance(summ["total_rain_mm"], (int, float)) else None,
                    "score": sc,
                    "tag": ("Excellent" if sc >= 80 else "Good" if sc >= 60 else "Moderate" if sc >= 40 else "Low"),
                    "rule": {"temp_min": r.temp_min, "temp_max": r.temp_max, "rain_min": r.rain_min, "rain_max": r.rain_max},
                }
            )
        crops.sort(key=lambda x: x["score"], reverse=True)

        return {
            "state": place.name,
            "lat": place.lat,
            "lon": place.lon,
            "season": season,
            "metrics": summ,
            "crops": crops,
        }
