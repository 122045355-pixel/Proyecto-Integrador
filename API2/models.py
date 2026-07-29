from sqlalchemy import (Boolean,Column,ForeignKey,Integer,String,Text)
from sqlalchemy.orm import relationship

from database import Base


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)

    users = relationship(
        "User",
        back_populates="role"
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    email = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True
    )
    password_hash = Column(String(255), nullable=False)

    role_id = Column(
        Integer,
        ForeignKey("roles.id"),
        nullable=False
    )

    is_active = Column(Boolean, nullable=False, default=True)

    role = relationship(
        "Role",
        back_populates="users"
    )