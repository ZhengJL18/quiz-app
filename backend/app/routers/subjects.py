"""Subjects CRUD router."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.engine import get_db
from app.db.models import User, Subject
from app.dependencies import get_current_user
from app.schemas.subject import SubjectCreate, SubjectUpdate, SubjectOut

router = APIRouter()


@router.get("", response_model=list[SubjectOut])
def list_subjects(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return db.query(Subject).filter_by(is_active=True).order_by(Subject.order_index).all()


@router.get("/{subject_id}", response_model=SubjectOut)
def get_subject(subject_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    subj = db.query(Subject).filter_by(id=subject_id, is_active=True).first()
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subj


@router.post("", response_model=SubjectOut, status_code=201)
def create_subject(body: SubjectCreate, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    subj = Subject(**body.model_dump())
    db.add(subj)
    db.commit()
    db.refresh(subj)
    return subj


@router.put("/{subject_id}", response_model=SubjectOut)
def update_subject(subject_id: int, body: SubjectUpdate, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    subj = db.query(Subject).filter_by(id=subject_id).first()
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")
    for key, val in body.model_dump(exclude_unset=True).items():
        setattr(subj, key, val)
    db.commit()
    db.refresh(subj)
    return subj


@router.delete("/{subject_id}", status_code=204)
def delete_subject(subject_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    subj = db.query(Subject).filter_by(id=subject_id).first()
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")
    subj.is_active = False
    db.commit()
    return None
