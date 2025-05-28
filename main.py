from typing import List
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload

from . import crud, schemas, auth, models
from .database import get_db
from .models import User

app = FastAPI()

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Auth endpoints
@app.post("/register", response_model=schemas.UserResponse)
async def register(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = crud.user_crud.get(db=db, username=user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    return crud.user_crud.create(db=db, **user_data.dict())


@app.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = await auth.authenticate_user(
        db, form_data.username, form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


# User profile endpoints
@app.get("/users/me", response_model=schemas.UserResponse)
async def read_users_me(
    current_user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    user = (
        db.query(models.User)
        .options(joinedload(models.User.selected_olympiads))
        .filter(models.User.id == current_user.id)
        .first()
    )
    return schemas.UserResponse.from_orm(user)


@app.put("/profile", response_model=schemas.UserResponse)
async def update_profile(
        user_update: schemas.UserUpdate,
        current_user: User = Depends(auth.get_current_user),
        db: Session = Depends(get_db)
):
    updated_user = crud.user_crud.update(
        db=db,
        filters={"id": current_user.id},
        **user_update.dict(exclude_unset=True)
    )

    db.refresh(updated_user)
    user_with_olympiads = (
        db.query(models.User)
        .options(joinedload(models.User.selected_olympiads))
        .filter(models.User.id == updated_user.id)
        .first()
    )

    return schemas.UserResponse.from_orm(user_with_olympiads)


@app.get("/profile", response_model=schemas.UserResponse)
async def get_profile_data(
    current_user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    user = (
        db.query(models.User)
        .options(joinedload(models.User.selected_olympiads))
        .filter(models.User.id == current_user.id)
        .first()
    )
    return schemas.UserResponse.from_orm(user)


@app.get("/all-olympiads", response_model=List[schemas.OlympiadResponse])
async def get_all_olympiads(db: Session = Depends(get_db)):
    return db.query(models.Olympiad).all()


# Olympiad endpoints
@app.get("/olympiads", response_model=List[schemas.OlympiadResponse])
async def get_olympiads(
        filters: schemas.FilterSettings = Depends(),
        db: Session = Depends(get_db)
):
    olympiads = crud.filter_service.get_filtered_olympiads(db, filters.dict(exclude_unset=True))

    return [
        schemas.OlympiadResponse(
            **{k: v for k, v in olympiad.__dict__.items() if k != "subjects"},
            subjects=olympiad.parsed_subjects,
            status=olympiad.status
        )
        for olympiad in olympiads
    ]


# Comments endpoints
@app.post("/olympiads/{olympiad_id}/comments", response_model=schemas.CommentResponse)
async def create_comment(
    olympiad_id: int,
    comment: schemas.CommentCreate,
    current_user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    return crud.comment_service.create_comment(
        db=db,
        user_id=current_user.id,
        olympiad_id=olympiad_id,
        text=comment.text
    )


@app.get("/olympiads/{olympiad_id}/comments", response_model=List[schemas.CommentResponse])
async def get_olympiad_comments(
    olympiad_id: int,
    db: Session = Depends(get_db)
):
    return crud.comment_service.get_comments_for_olympiad(db=db, olympiad_id=olympiad_id)


# Participation endpoints
@app.post("/participations", response_model=schemas.ParticipationResponse)
async def create_participation(
    participation: schemas.ParticipationBase,
    current_user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    return crud.participation_service.create_participation(
        db=db,
        user_id=current_user.id,
        olympiad_id=participation.olympiad_id
    )


@app.delete("/participations/{olympiad_id}")
async def delete_participation(
    olympiad_id: int,
    current_user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    success = crud.participation_service.delete_participation(
        db=db,
        user_id=current_user.id,
        olympiad_id=olympiad_id
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participation not found"
        )
    return {"status": "success"}


# Notifications endpoints
@app.get("/notifications", response_model=List[schemas.NotificationResponse])
async def get_notifications(
    current_user: User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    return crud.notification_service.get_unread_notifications(
        db=db,
        user_id=current_user.id
    )