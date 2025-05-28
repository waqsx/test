from typing import Any, Dict, List, Optional, Type, TypeVar
from sqlalchemy import and_, exc, func
from sqlalchemy.orm import Session, joinedload
from backend.models import Base, User, Olympiad, Participation, Notification, Comment
from passlib.context import CryptContext
from backend.auth import get_password_hash
import json

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ModelType = TypeVar("ModelType", bound=Base)


class BaseCRUD:
    """Базовый класс для CRUD-операций с моделями SQLAlchemy."""

    def __init__(self, model: Type[ModelType]):
        self.model = model

    def create(self, db: Session, **data: Any) -> Optional[ModelType]:
        """Создание нового объекта в базе данных."""

        try:
            if self.model == User and "password" in data:
                data["password"] = get_password_hash(data.pop("password"))
            if "subjects" in data and isinstance(data["subjects"], list):
                data["subjects"] = json.dumps(data["subjects"], ensure_ascii=False)
            obj = self.model(**data)
            db.add(obj)
            db.commit()
            db.refresh(obj)
            return obj
        except exc.SQLAlchemyError as e:
            db.rollback()
            raise e

    def get(self, db: Session, **filters: Any) -> Optional[ModelType]:
        """Получение одного объекта по фильтрам."""
        return db.query(self.model).filter_by(**filters).first()

    def get_all(
            self,
            db: Session,
            *,
            skip: int = 0,
            limit: int = 100,
            **filters: Any
    ) -> List[ModelType]:
        """Получение списка объектов с пагинацией и фильтрацией."""
        query = db.query(self.model)
        if filters:
            query = query.filter_by(**filters)
        return query.offset(skip).limit(limit).all()

    def update(self, db: Session, filters: Dict[str, Any], **data: Any) -> Optional[ModelType]:
        obj = self.get(db, **filters)
        if not obj:
            return None

        try:
            if "selected_olympiads" in data:
                olympiad_ids = data.pop("selected_olympiads")
                olympiads = db.query(Olympiad).filter(Olympiad.id.in_(olympiad_ids)).all()
                obj.selected_olympiads = olympiads

            for key, value in data.items():
                setattr(obj, key, value)

            db.commit()
            db.refresh(obj)
            return obj
        except exc.SQLAlchemyError as e:
            db.rollback()
            raise e

    def delete(self, db: Session, **filters: Any) -> bool:
        """Удаление объекта по фильтрам."""
        obj = self.get(db, **filters)
        if not obj:
            return False
        try:
            db.delete(obj)
            db.commit()
            return True
        except exc.SQLAlchemyError as e:
            db.rollback()
            raise e


class SubscriptionService:
    """Сервис управления подписками пользователей на олимпиады."""

    def __init__(self, user_crud: BaseCRUD, olympiad_crud: BaseCRUD):
        self.user_crud = user_crud
        self.olympiad_crud = olympiad_crud

    def add_subscription(
            self,
            db: Session,
            user_id: int,
            olympiad_id: int
    ) -> bool:
        """Добавление подписки пользователя на олимпиаду."""
        user = self.user_crud.get(db, id=user_id)
        olympiad = self.olympiad_crud.get(db, id=olympiad_id)

        if not user or not olympiad:
            return False

        if olympiad not in user.selected_olympiads:
            user.selected_olympiads.append(olympiad)
            db.commit()
            return True
        return False

    def remove_subscription(
            self,
            db: Session,
            user_id: int,
            olympiad_id: int
    ) -> bool:
        """Удаление подписки пользователя на олимпиаду."""
        user = self.user_crud.get(db, id=user_id)
        olympiad = self.olympiad_crud.get(db, id=olympiad_id)

        if not user or not olympiad:
            return False

        try:
            user.selected_olympiads.remove(olympiad)
            db.commit()
            return True
        except ValueError:
            return False


class ParticipationService:
    """Сервис управления участием в олимпиадах."""

    def __init__(self, participation_crud: BaseCRUD):
        self.crud = participation_crud

    def create_participation(
            self,
            db: Session,
            user_id: int,
            olympiad_id: int
    ) -> Participation:
        """Создание записи об участии пользователя в олимпиаде."""
        return self.crud.create(
            db,
            user_id=user_id,
            olympiad_id=olympiad_id
        )

    def delete_participation(
            self,
            db: Session,
            user_id: int,
            olympiad_id: int
    ) -> bool:
        """Удаление записи об участии по связке user_id/olympiad_id."""
        result = db.query(Participation).filter(
            and_(
                Participation.user_id == user_id,
                Participation.olympiad_id == olympiad_id
            )
        ).delete()
        db.commit()
        return result > 0


class NotificationService:
    """Сервис работы с уведомлениями пользователей."""

    def get_unread_notifications(
            self,
            db: Session,
            user_id: int
    ) -> List[Notification]:
        """Получение непрочитанных уведомлений с информацией об олимпиадах."""
        return db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).options(joinedload(Notification.olympiad)).all()


class OlympiadFilterService:
    """Сервис фильтрации олимпиад по различным критериям."""

    def get_filtered_olympiads(self, db: Session, filters: Dict[str, Any]) -> List[Olympiad]:
        query = db.query(Olympiad)

        if levels := filters.get("levels"):
            query = query.filter(Olympiad.level.in_(levels))

        if subjects := filters.get("subjects"):
            # Используем JSON-содержимое для фильтрации
            subjects_conditions = []
            for subj in subjects:
                subjects_conditions.append(
                    func.json_contains(Olympiad.subjects, json.dumps(subj))
                )
            query = query.filter(and_(*subjects_conditions))

        if universities := filters.get("universities"):
            query = query.filter(Olympiad.university.in_(universities))

        return query.all()


class CommentService:
    """Сервис работы с комментариями к олимпиадам."""

    def __init__(self, comment_crud: BaseCRUD):
        self.crud = comment_crud

    def create_comment(
            self,
            db: Session,
            user_id: int,
            olympiad_id: int,
            text: str
    ) -> Comment:
        """Создание нового комментария."""
        return self.crud.create(
            db,
            text=text,
            author_id=user_id,
            olympiad_id=olympiad_id
        )

    def get_comments_for_olympiad(
            self,
            db: Session,
            olympiad_id: int
    ) -> List[Comment]:
        """Получение комментариев с информацией об авторах."""
        return db.query(Comment).filter(
            Comment.olympiad_id == olympiad_id
        ).options(joinedload(Comment.author)).all()


# Инициализация зависимостей
user_crud = BaseCRUD(User)
olympiad_crud = BaseCRUD(Olympiad)
participation_crud = BaseCRUD(Participation)
comment_crud = BaseCRUD(Comment)

subscription_service = SubscriptionService(user_crud, olympiad_crud)
participation_service = ParticipationService(participation_crud)
filter_service = OlympiadFilterService()
comment_service = CommentService(comment_crud)
notification_service = NotificationService()