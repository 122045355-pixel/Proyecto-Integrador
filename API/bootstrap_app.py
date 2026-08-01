import os

from fastapi import Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import get_db
from main_v4 import app, crear_token, generar_password_hash, validar_api_key
from models import Role, User


DEFAULT_CORS_ORIGINS = (
    "http://localhost:8082,"
    "http://127.0.0.1:8082,"
    "http://localhost:19006,"
    "http://127.0.0.1:19006"
)

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class BootstrapAdminCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


@app.post("/api/bootstrap/admin")
def crear_primer_admin(
    datos: BootstrapAdminCreate,
    api_key_valida: bool = Depends(validar_api_key),
    db: Session = Depends(get_db),
):
    usuarios_existentes = db.query(User).count()

    if usuarios_existentes > 0:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Bootstrap bloqueado",
                "mensaje": "Ya existen usuarios. Inicia sesion como admin_ti o admin para crear mas usuarios."
            }
        )

    rol = db.query(Role).filter(Role.name == "admin_ti").first()

    if not rol:
        rol = Role(
            name="admin_ti",
            description="Administrador tecnico inicial del sistema"
        )
        db.add(rol)
        db.commit()
        db.refresh(rol)

    usuario = User(
        name=datos.name,
        email=datos.email,
        password_hash=generar_password_hash(datos.password),
        role_id=rol.id,
        is_active=True,
    )

    db.add(usuario)
    db.commit()
    db.refresh(usuario)

    token = crear_token(usuario)

    return {
        "mensaje": "Primer administrador creado correctamente",
        "access_token": token,
        "token_type": "bearer",
        "usuario": {
            "id": usuario.id,
            "name": usuario.name,
            "email": usuario.email,
            "role": usuario.role.name,
        }
    }
