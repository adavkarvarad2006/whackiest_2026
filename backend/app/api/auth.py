"""Authentication endpoints: register/signup, login, demo account, and profile."""

from pathlib import Path
import shutil
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.config import get_settings
from app.database import get_db
from app.models import Document, User
from app.schemas import TokenResponse, UserLogin, UserOut, UserRegister
from app.services.ingestion import process_existing_document

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _register_user(payload: UserRegister, db: Session) -> TokenResponse:
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    user = User(
        name=payload.name.strip(),
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    return _register_user(payload, db)


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: UserRegister, db: Session = Depends(get_db)):
    """Alias for /register used by the Next.js frontend."""
    return _register_user(payload, db)


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    token = create_access_token(user.id, user.email)
    out = UserOut.model_validate(user)
    out.is_demo = user.email.endswith(".demo@arthalens.example")
    return TokenResponse(access_token=token, user=out)


@router.post("/demo", response_model=TokenResponse)
def demo_login(db: Session = Depends(get_db)):
    """Sign into the synthetic demo profile and seed ArthaLens_Demo_Dataset PDFs if empty."""
    demo_email = "ananya.demo@arthalens.example"
    user = db.scalar(select(User).where(User.email == demo_email))
    if user is None:
        user = User(
            name="Ananya Sharma (Demo)",
            email=demo_email,
            hashed_password=hash_password("DemoOnlyPassword123!"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    doc_count = db.scalar(select(func.count(Document.id)).where(Document.user_id == user.id)) or 0
    if doc_count == 0:
        demo_docs_dir = Path(__file__).resolve().parents[3] / "ArthaLens_Demo_Dataset" / "Documents"
        if demo_docs_dir.exists():
            settings = get_settings()
            user_dir = settings.storage_path / str(user.id)
            user_dir.mkdir(parents=True, exist_ok=True)
            for pdf_path in sorted(demo_docs_dir.glob("*.pdf")):
                dest = user_dir / f"{uuid.uuid4().hex}_{pdf_path.name}"
                shutil.copy2(pdf_path, dest)
                import hashlib
                h = hashlib.sha256(dest.read_bytes()).hexdigest()
                doc = Document(
                    user_id=user.id,
                    filename=pdf_path.name,
                    document_type="PENDING_CLASSIFICATION",
                    file_hash=h,
                    file_path=str(dest),
                    file_size_bytes=dest.stat().st_size,
                    page_count=0,
                    processing_status="PENDING",
                )
                db.add(doc)
                db.commit()
                db.refresh(doc)
                process_existing_document(db, doc)

    token = create_access_token(user.id, user.email)
    out = UserOut.model_validate(user)
    out.is_demo = True
    return TokenResponse(access_token=token, user=out)


class UserProfileUpdate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    out = UserOut.model_validate(current_user)
    out.is_demo = current_user.email.endswith(".demo@arthalens.example")
    return out


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.name = payload.name.strip()
    db.commit()
    db.refresh(current_user)
    out = UserOut.model_validate(current_user)
    out.is_demo = current_user.email.endswith(".demo@arthalens.example")
    return out
