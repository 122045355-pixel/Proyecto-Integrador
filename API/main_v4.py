import os
from datetime import datetime, timedelta, timezone

import bcrypt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import get_db
from models import Role, User


load_dotenv()

app = FastAPI(
    title="API de Gestión Documental",
    description=(
        "API con API Key, autenticación JWT, roles "
        "y protección de acceso a recursos."
    ),
    version="1.0.0"
)

API_KEY_VALIDA = os.getenv("API_KEY")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

bearer_scheme = HTTPBearer(auto_error=False)


# =========================================================
# SCHEMAS
# =========================================================

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role_id: int


# =========================================================
# API KEY
# =========================================================

def validar_api_key(
    x_api_key: str | None = Header(
        default=None,
        alias="x-api-key"
    )
):
    if not API_KEY_VALIDA:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Configuración incompleta",
                "mensaje": "La variable API_KEY no está configurada"
            }
        )

    if x_api_key != API_KEY_VALIDA:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "No autorizado",
                "mensaje": "API Key inválida o no enviada"
            }
        )

    return True


# =========================================================
# CONTRASEÑAS
# =========================================================

def verificar_password(
    password_plano: str,
    password_hash: str
) -> bool:
    password_hash = password_hash.replace("$2y$", "$2b$")

    return bcrypt.checkpw(
        password_plano.encode("utf-8"),
        password_hash.encode("utf-8")
    )


def generar_password_hash(password: str) -> str:
    password_bytes = password.encode("utf-8")

    hash_generado = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt()
    )

    return hash_generado.decode("utf-8")


# =========================================================
# JWT
# =========================================================

def crear_token(usuario: User) -> str:
    expiracion = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(usuario.id),
        "name": usuario.name,
        "email": usuario.email,
        "role": usuario.role.name,
        "exp": expiracion
    }

    token = jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM
    )

    return token


def obtener_usuario_actual(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db)
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "No autorizado",
                "mensaje": "Token JWT no enviado"
            }
        )

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
        )

        usuario_id = payload.get("sub")

        if usuario_id is None:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "Token inválido",
                    "mensaje": (
                        "El token no contiene la identidad "
                        "del usuario"
                    )
                }
            )

        usuario_id = int(usuario_id)

    except (JWTError, ValueError):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Token inválido",
                "mensaje": "El token es inválido o expiró"
            }
        )

    usuario = (
        db.query(User)
        .filter(User.id == usuario_id)
        .first()
    )

    if not usuario:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Usuario no encontrado"
            }
        )

    if not usuario.is_active:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Usuario inactivo",
                "mensaje": "La cuenta se encuentra desactivada"
            }
        )

    return usuario


# =========================================================
# AUTORIZACIÓN POR ROL
# =========================================================

def requiere_rol(*roles_permitidos: str):
    def dependencia(
        usuario_actual: User = Depends(
            obtener_usuario_actual
        )
    ) -> User:
        if usuario_actual.role.name not in roles_permitidos:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Acceso denegado",
                    "mensaje": (
                        "No tienes el rol necesario "
                        "para realizar esta acción"
                    )
                }
            )

        return usuario_actual

    return dependencia


# =========================================================
# LOGIN
# =========================================================

@app.post("/login")
def login(
    datos: LoginRequest,
    api_key_valida: bool = Depends(validar_api_key),
    db: Session = Depends(get_db)
):
    usuario = (
        db.query(User)
        .filter(User.email == datos.email)
        .first()
    )

    if not usuario:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Credenciales inválidas"
            }
        )

    if not usuario.is_active:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Cuenta inactiva"
            }
        )

    if not verificar_password(
        datos.password,
        usuario.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Credenciales inválidas"
            }
        )

    token = crear_token(usuario)

    return {
        "mensaje": "Login exitoso",
        "access_token": token,
        "token_type": "bearer",
        "usuario": {
            "id": usuario.id,
            "name": usuario.name,
            "email": usuario.email,
            "role": usuario.role.name
        }
    }


# =========================================================
# PERFIL
# =========================================================

@app.get("/api/perfil")
def perfil(
    api_key_valida: bool = Depends(validar_api_key),
    usuario_actual: User = Depends(
        obtener_usuario_actual
    )
):
    return {
        "user_id": usuario_actual.id,
        "name": usuario_actual.name,
        "email": usuario_actual.email,
        "role": usuario_actual.role.name,
        "is_active": usuario_actual.is_active,
        "created_at": usuario_actual.created_at,
        "updated_at": usuario_actual.updated_at
    }


# =========================================================
# USUARIOS
# =========================================================

@app.get("/api/users")
def obtener_usuarios(
    api_key_valida: bool = Depends(validar_api_key),
    usuario_actual: User = Depends(
        requiere_rol("admin")
    ),
    db: Session = Depends(get_db)
):
    usuarios = db.query(User).all()

    return [
        {
            "id": usuario.id,
            "name": usuario.name,
            "email": usuario.email,
            "role": usuario.role.name,
            "is_active": usuario.is_active,
            "created_at": usuario.created_at
        }
        for usuario in usuarios
    ]


@app.get("/api/users/{user_id}")
def obtener_usuario_por_id(
    user_id: int,
    api_key_valida: bool = Depends(validar_api_key),
    usuario_actual: User = Depends(
        obtener_usuario_actual
    ),
    db: Session = Depends(get_db)
):
    usuario = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not usuario:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Usuario no encontrado"
            }
        )

    es_mismo_usuario = usuario_actual.id == user_id
    es_admin = usuario_actual.role.name == "admin"

    if not es_mismo_usuario and not es_admin:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Acceso denegado",
                "mensaje": (
                    "No puedes consultar la información "
                    "de otro usuario"
                )
            }
        )

    return {
        "id": usuario.id,
        "name": usuario.name,
        "email": usuario.email,
        "role": usuario.role.name,
        "is_active": usuario.is_active,
        "created_at": usuario.created_at,
        "updated_at": usuario.updated_at
    }


@app.post("/api/users")
def crear_usuario(
    datos: UserCreate,
    api_key_valida: bool = Depends(validar_api_key),
    usuario_actual: User = Depends(
        requiere_rol("admin")
    ),
    db: Session = Depends(get_db)
):
    usuario_existente = (
        db.query(User)
        .filter(User.email == datos.email)
        .first()
    )

    if usuario_existente:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Correo ya registrado"
            }
        )

    rol = (
        db.query(Role)
        .filter(Role.id == datos.role_id)
        .first()
    )

    if not rol:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Rol no encontrado"
            }
        )

    nuevo_usuario = User(
        name=datos.name,
        email=datos.email,
        password_hash=generar_password_hash(
            datos.password
        ),
        role_id=datos.role_id,
        is_active=True
    )

    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    return {
        "mensaje": "Usuario creado correctamente",
        "usuario": {
            "id": nuevo_usuario.id,
            "name": nuevo_usuario.name,
            "email": nuevo_usuario.email,
            "role": nuevo_usuario.role.name,
            "is_active": nuevo_usuario.is_active
        }
    }


# =========================================================
# ROLES
# =========================================================

@app.get("/api/roles")
def obtener_roles(
    api_key_valida: bool = Depends(validar_api_key),
    usuario_actual: User = Depends(
        requiere_rol("admin")
    ),
    db: Session = Depends(get_db)
):
    roles = db.query(Role).all()

    return [
        {
            "id": rol.id,
            "name": rol.name,
            "description": rol.description
        }
        for rol in roles
    ]