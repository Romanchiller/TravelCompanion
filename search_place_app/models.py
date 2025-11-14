from sqlalchemy import VARCHAR, Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base, int_pk, str_null_true, str_uniq
from sqlalchemy import UniqueConstraint


class User(Base):
    __tablename__ = "user"
    id: Mapped[int_pk]
    name: Mapped[str_null_true] = mapped_column(VARCHAR(100), nullable=False)
    email: Mapped[str_uniq] = mapped_column(VARCHAR(100), nullable=False)
    password: Mapped[str_null_true] = mapped_column(VARCHAR(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    places = relationship("Place", secondary="user_place", back_populates="users", lazy="selectin")
    categories = relationship("Category", secondary="user_category", back_populates="users", lazy="selectin")

    @property
    def dict(self):
        return {"id": self.id,
                "name": self.name,
                "email": self.email}

class PlaceCategory(Base):
    __tablename__ = "place_category"
    id: Mapped[int_pk]
    place_id: Mapped[int] = mapped_column(ForeignKey("place.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("category.id"), nullable=False)

class Place(Base):
    __tablename__ = "place"
    id: Mapped[int_pk]
    name: Mapped[str_null_true] = mapped_column(VARCHAR(255), nullable=False)
    address: Mapped[str_null_true] = mapped_column(VARCHAR(255), nullable=True)
    categories = relationship("Category", secondary="place_category", back_populates="places", lazy="selectin")
    users = relationship("User", secondary="user_place", back_populates="places", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("name", "address", name="uq_place_name_address"),
    )

class Category(Base):
    __tablename__ = "category"
    id: Mapped[int_pk]
    name: Mapped[str_null_true] = mapped_column(VARCHAR(255), nullable=False, unique=True)
    places = relationship("Place", secondary="place_category", back_populates="categories", lazy="selectin")
    users = relationship("User", secondary="user_category", back_populates="categories", lazy="selectin")

class UserPlace(Base):
    __tablename__ = "user_place"
    id: Mapped[int_pk]
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    place_id: Mapped[int] = mapped_column(ForeignKey("place.id"), nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        UniqueConstraint("user_id", "place_id", name="uq_user_place"),
    )


class UserCategory(Base):
    __tablename__ = "user_category"
    id: Mapped[int_pk]
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("category.id"), nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        UniqueConstraint("user_id", "category_id", name="uq_user_category"),
    )