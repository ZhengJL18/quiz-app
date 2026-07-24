"""Subjects CRUD router — SQLite for web API, vault for content storage."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.engine import get_db
from app.db.models import User, Subject
from app.dependencies import get_current_user
from app.schemas.subject import SubjectCreate, SubjectUpdate, SubjectOut
from app.vault import manager as vault

router = APIRouter()


@router.get("", response_model=list[SubjectOut])
def list_subjects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Subject).filter(Subject.user_id == current_user.id, Subject.is_active == True).order_by(Subject.order_index).all()


@router.get("/{subject_id}", response_model=SubjectOut)
def get_subject(subject_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    subj = db.query(Subject).filter_by(id=subject_id, user_id=current_user.id, is_active=True).first()
    if not subj: raise HTTPException(status_code=404, detail="Subject not found")
    return subj


@router.post("", response_model=SubjectOut, status_code=201)
def create_subject(body: SubjectCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    subj = Subject(user_id=current_user.id, **body.model_dump())
    db.add(subj); db.commit(); db.refresh(subj)
    # Also create vault folder
    vault.ensure_subject(subj.name, subj.description or "", subj.prompt_style or "")
    return subj


@router.put("/{subject_id}", response_model=SubjectOut)
def update_subject(subject_id: int, body: SubjectUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    subj = db.query(Subject).filter_by(id=subject_id, user_id=current_user.id).first()
    if not subj: raise HTTPException(status_code=404)
    old_name = subj.name
    for key, val in body.model_dump(exclude_unset=True).items():
        setattr(subj, key, val)
    db.commit(); db.refresh(subj)
    # Sync vault
    if body.name and body.name != old_name:
        vault.rename_subject(old_name, body.name)
    return subj


@router.delete("/{subject_id}", status_code=204)
def delete_subject(subject_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    subj = db.query(Subject).filter_by(id=subject_id, user_id=current_user.id).first()
    if not subj: raise HTTPException(status_code=404)
    vault.delete_subject(subj.name)
    subj.is_active = False
    db.commit()
    return None
