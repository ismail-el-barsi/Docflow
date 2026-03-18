"""Routes d'authentification — register / login."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.database import get_db
from app.schemas.user import TokenResponse, UserCreate, UserOut, UserRole

router = APIRouter(prefix="/api/auth", tags=["auth"])

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_JWT_SECRET = os.getenv("JWT_SECRET", "docflow_jwt_secret_2026")
_JWT_ALGO = "HS256"
_JWT_EXPIRE_MINUTES = 60 * 24  # 24h


# ── helpers ──────────────────────────────────────────────────────────────────

def _hash(password: str) -> str:
    return _pwd.hash(password)


def _verify(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def _create_token(sub: str, role: str, email: str, full_name: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=_JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": sub, "role": role, "email": email, "full_name": full_name, "exp": expire}, _JWT_SECRET, algorithm=_JWT_ALGO)


def _doc_to_user_out(doc: dict) -> UserOut:
    return UserOut(
        id=str(doc["_id"]),
        email=doc["email"],
        full_name=doc["full_name"],
        role=doc["role"],
        created_at=doc["created_at"],
    )


# ── routes ───────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate):
    db = get_db()
    if await db.users.find_one({"email": body.email}):
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    doc = {
        "email": body.email,
        "full_name": body.full_name,
        "hashed_password": _hash(body.password),
        "role": body.role.value,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_user_out(doc)


@router.post("/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends()):
    db = get_db()
    doc = await db.users.find_one({"email": form.username})
    if not doc or not _verify(form.password, doc["hashed_password"]):
        raise HTTPException(status_code=401, detail="Identifiants invalides")

    token = _create_token(sub=str(doc["_id"]), role=doc["role"], email=doc["email"], full_name=doc["full_name"])
    return TokenResponse(access_token=token, user=_doc_to_user_out(doc))


@router.get("/me", response_model=UserOut)
async def me(token: str = Depends(_oauth2)):
    try:
        payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGO])
        user_id: str = payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide")

    from bson import ObjectId
    db = get_db()
    doc = await db.users.find_one({"_id": ObjectId(user_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return _doc_to_user_out(doc)


# ── dependency injectable ─────────────────────────────────────────────────────

async def require_auth(token: str = Depends(_oauth2)) -> dict:
    """Dependency — retourne le payload JWT décodé."""
    try:
        return jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGO])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide")


async def require_admin(payload: dict = Depends(require_auth)) -> dict:
    """Dependency — vérifie que l'utilisateur est admin."""
    if payload.get("role") != UserRole.admin.value:
        raise HTTPException(status_code=403, detail="Accès réservé aux admins")
    return payload
