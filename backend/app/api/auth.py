"""
Auth routes — sign up, sign in, profile management via Supabase Auth.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from supabase import Client

from app.database import get_supabase
from app.api.deps import get_current_user, get_db

router = APIRouter()


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    name: str = ""


class SignInRequest(BaseModel):
    email: EmailStr
    password: str


class ProfileUpdate(BaseModel):
    name: str | None = None


@router.post("/signup")
async def sign_up(req: SignUpRequest):
    sb = get_supabase()
    try:
        result = sb.auth.sign_up({
            "email": req.email,
            "password": req.password,
            "options": {
                "data": {"name": req.name}
            }
        })
        return {
            "user_id": result.user.id if result.user else None,
            "message": "Регистрация успешна. Проверьте email для подтверждения.",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/signin")
async def sign_in(req: SignInRequest):
    sb = get_supabase()
    try:
        result = sb.auth.sign_in_with_password({
            "email": req.email,
            "password": req.password,
        })
        return {
            "access_token": result.session.access_token,
            "refresh_token": result.session.refresh_token,
            "user": {
                "id": result.user.id,
                "email": result.user.email,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")


@router.post("/refresh")
async def refresh_token(refresh_token: str):
    sb = get_supabase()
    try:
        result = sb.auth.refresh_session(refresh_token)
        return {
            "access_token": result.session.access_token,
            "refresh_token": result.session.refresh_token,
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.get("/me")
async def get_me(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    result = db.table("profiles").select("*").eq("id", user["id"]).single().execute()
    return result.data


@router.patch("/me")
async def update_me(
    update: ProfileUpdate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    data = {k: v for k, v in update.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="Nothing to update")

    result = db.table("profiles").update(data).eq("id", user["id"]).execute()
    return result.data[0] if result.data else {}


@router.post("/signout")
async def sign_out():
    sb = get_supabase()
    sb.auth.sign_out()
    return {"message": "Signed out"}
