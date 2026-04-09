"""
Carousel Templates API.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import Client

from app.api.deps import get_current_user, get_db

router = APIRouter()


class TemplateCreate(BaseModel):
    name: str
    type: str  # "topic" | "property"
    style_params: dict
    is_default: bool = False


class TemplateUpdate(BaseModel):
    name: str | None = None
    style_params: dict | None = None
    is_default: bool | None = None


@router.get("")
async def list_templates(
    type: str | None = None,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    query = db.table("carousel_templates").select("*")
    if type:
        query = query.eq("type", type)
    result = query.order("is_default", desc=True).execute()
    return result.data


@router.get("/{template_id}")
async def get_template(
    template_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    result = db.table("carousel_templates").select("*").eq("id", template_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Template not found")
    return result.data


@router.post("")
async def create_template(
    req: TemplateCreate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    result = db.table("carousel_templates").insert(req.model_dump()).execute()
    return result.data[0] if result.data else {}


@router.patch("/{template_id}")
async def update_template(
    template_id: str,
    req: TemplateUpdate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="Nothing to update")
    result = db.table("carousel_templates").update(data).eq("id", template_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Template not found")
    return result.data[0]
