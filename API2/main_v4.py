import os
from datetime import datetime, timedelta, timezone

import bcrypt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import get_db
from models import (
    ApprovalRequest,
    CaseParticipant,
    DocumentAccessEvent,
    LegalCase,
    LegalDocument,
    LegalDocumentVersion,
    Role,
    SignatureEvent,
    SignatureRequest,
    User,
)


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


class ApprovalCreate(BaseModel):
    reviewer_id: int | None = None
    comment: str | None = None


class ApprovalDecision(BaseModel):
    decision: str
    comment: str | None = None


class SignatureRequestCreate(BaseModel):
    signer_id: int
    signing_order: int = 1
    mode: str = "sequential"


class SignatureSign(BaseModel):
    document_version_id: int
    signature_hash: str
    signed_payload: dict | None = None


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


def es_rol_global(usuario: User) -> bool:
    return usuario.role.name in {"admin", "admin_ti", "juez", "notario"}


def registrar_evento_documento(
    db: Session,
    usuario: User,
    documento_id: int,
    accion: str,
    canal: str,
    permitido: bool,
    razon: str | None,
    request: Request | None = None
):
    evento = DocumentAccessEvent(
        user_id=usuario.id if usuario else None,
        document_id=documento_id,
        action=accion,
        channel=canal,
        allowed=permitido,
        reason=razon,
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None
    )
    db.add(evento)
    db.commit()


def obtener_participacion(
    db: Session,
    case_id: int,
    usuario: User
) -> CaseParticipant | None:
    return (
        db.query(CaseParticipant)
        .filter(
            CaseParticipant.case_id == case_id,
            CaseParticipant.user_id == usuario.id
        )
        .first()
    )


def puede_ver_caso(db: Session, caso: LegalCase, usuario: User) -> bool:
    if es_rol_global(usuario):
        return caso.status == "active" or usuario.role.name in {"admin", "admin_ti", "notario"}

    return obtener_participacion(db, caso.id, usuario) is not None


def puede_ver_documento(db: Session, documento: LegalDocument, usuario: User) -> bool:
    if es_rol_global(usuario):
        return documento.case.status == "active" or usuario.role.name in {"admin", "admin_ti", "notario"}

    if documento.owner_id == usuario.id:
        return True

    participacion = obtener_participacion(db, documento.case_id, usuario)

    if not participacion:
        return False

    if participacion.role_name == "abogado":
        return (
            documento.document_type.classification == "libelo"
            and participacion.represented_user_id == documento.owner_id
        )

    return False


def obtener_documento_autorizado(
    db: Session,
    document_id: int,
    usuario: User
) -> LegalDocument:
    documento = (
        db.query(LegalDocument)
        .filter(LegalDocument.id == document_id)
        .first()
    )

    if not documento:
        raise HTTPException(
            status_code=404,
            detail={"error": "Documento no encontrado"}
        )

    if not puede_ver_documento(db, documento, usuario):
        raise HTTPException(
            status_code=403,
            detail={"error": "No tienes acceso a este documento"}
        )

    return documento


def serializar_caso(caso: LegalCase):
    return {
        "id": caso.id,
        "title": caso.title,
        "description": caso.description,
        "status": caso.status,
        "created_by": caso.created_by,
        "created_at": caso.created_at,
        "updated_at": caso.updated_at,
        "archived_at": caso.archived_at
    }


def serializar_documento(documento: LegalDocument):
    return {
        "id": documento.id,
        "case_id": documento.case_id,
        "owner_id": documento.owner_id,
        "title": documento.title,
        "description": documento.description,
        "status": documento.status,
        "current_version": documento.current_version,
        "classification": documento.document_type.classification,
        "document_type": documento.document_type.name,
        "requires_ocr": documento.document_type.requires_ocr,
        "requires_approval": documento.document_type.requires_approval,
        "requires_signature": documento.document_type.requires_signature,
        "created_at": documento.created_at,
        "updated_at": documento.updated_at,
        "archived_at": documento.archived_at
    }


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
        requiere_rol("admin", "admin_ti")
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
    es_admin = usuario_actual.role.name in {"admin", "admin_ti"}

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
        requiere_rol("admin", "admin_ti")
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
        requiere_rol("admin", "admin_ti")
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


# =========================================================
# CASOS Y DOCUMENTOS LEGALES
# =========================================================

@app.get("/api/cases")
def obtener_casos(
    api_key_valida: bool = Depends(validar_api_key),
    usuario_actual: User = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    if es_rol_global(usuario_actual):
        consulta = db.query(LegalCase)

        if usuario_actual.role.name == "juez":
            consulta = consulta.filter(LegalCase.status == "active")

        casos = consulta.all()
    else:
        casos = (
            db.query(LegalCase)
            .join(CaseParticipant)
            .filter(CaseParticipant.user_id == usuario_actual.id)
            .all()
        )

    return [serializar_caso(caso) for caso in casos]


@app.get("/api/cases/{case_id}/documents")
def obtener_documentos_del_caso(
    case_id: int,
    api_key_valida: bool = Depends(validar_api_key),
    usuario_actual: User = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    caso = db.query(LegalCase).filter(LegalCase.id == case_id).first()

    if not caso:
        raise HTTPException(status_code=404, detail={"error": "Caso no encontrado"})

    if not puede_ver_caso(db, caso, usuario_actual):
        raise HTTPException(status_code=403, detail={"error": "No tienes acceso a este caso"})

    documentos = (
        db.query(LegalDocument)
        .filter(LegalDocument.case_id == case_id)
        .all()
    )

    return [
        serializar_documento(documento)
        for documento in documentos
        if puede_ver_documento(db, documento, usuario_actual)
    ]


@app.get("/api/documents/{document_id}/view")
def ver_documento(
    document_id: int,
    request: Request,
    x_client_channel: str = Header(default="api", alias="x-client-channel"),
    api_key_valida: bool = Depends(validar_api_key),
    usuario_actual: User = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    documento = obtener_documento_autorizado(db, document_id, usuario_actual)
    version = (
        db.query(LegalDocumentVersion)
        .filter(LegalDocumentVersion.document_id == document_id)
        .order_by(LegalDocumentVersion.version_number.desc())
        .first()
    )

    registrar_evento_documento(
        db,
        usuario_actual,
        document_id,
        "view",
        x_client_channel,
        True,
        "Vista autorizada",
        request
    )

    return {
        "document": serializar_documento(documento),
        "current_file": None if not version else {
            "version_number": version.version_number,
            "original_name": version.original_name,
            "content_type": version.content_type,
            "size_bytes": version.size_bytes,
            "sha256": version.sha256,
            "created_at": version.created_at
        },
        "download_allowed": False if x_client_channel == "mobile" else usuario_actual.role.name in {"juez", "notario"}
    }


@app.get("/api/documents/{document_id}/download")
def descargar_documento(
    document_id: int,
    request: Request,
    x_client_channel: str = Header(default="api", alias="x-client-channel"),
    api_key_valida: bool = Depends(validar_api_key),
    usuario_actual: User = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    documento = obtener_documento_autorizado(db, document_id, usuario_actual)

    if x_client_channel == "mobile":
        registrar_evento_documento(
            db,
            usuario_actual,
            document_id,
            "download",
            x_client_channel,
            False,
            "Descarga bloqueada en movil",
            request
        )
        raise HTTPException(
            status_code=403,
            detail={"error": "La descarga no esta permitida en la aplicacion movil"}
        )

    if usuario_actual.role.name not in {"juez", "notario"}:
        registrar_evento_documento(
            db,
            usuario_actual,
            document_id,
            "download",
            x_client_channel,
            False,
            "Rol sin permiso de descarga",
            request
        )
        raise HTTPException(
            status_code=403,
            detail={"error": "Solo jueces y notarios pueden descargar desde web"}
        )

    version = (
        db.query(LegalDocumentVersion)
        .filter(LegalDocumentVersion.document_id == documento.id)
        .order_by(LegalDocumentVersion.version_number.desc())
        .first()
    )

    if not version:
        raise HTTPException(status_code=404, detail={"error": "El documento no tiene versiones"})

    registrar_evento_documento(
        db,
        usuario_actual,
        document_id,
        "download",
        x_client_channel,
        True,
        "Descarga autorizada",
        request
    )

    return {
        "message": "Descarga autorizada",
        "document_id": documento.id,
        "version_number": version.version_number,
        "storage_path": version.storage_path,
        "sha256": version.sha256
    }


@app.post("/api/documents/{document_id}/approval-requests")
def crear_solicitud_aprobacion(
    document_id: int,
    datos: ApprovalCreate,
    api_key_valida: bool = Depends(validar_api_key),
    usuario_actual: User = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    documento = obtener_documento_autorizado(db, document_id, usuario_actual)

    solicitud = ApprovalRequest(
        document_id=documento.id,
        requested_by=usuario_actual.id,
        reviewer_id=datos.reviewer_id,
        status="pending",
        comment=datos.comment
    )
    documento.status = "under_review"

    db.add(solicitud)
    db.commit()
    db.refresh(solicitud)

    return {
        "id": solicitud.id,
        "document_id": solicitud.document_id,
        "status": solicitud.status,
        "requested_by": solicitud.requested_by,
        "reviewer_id": solicitud.reviewer_id
    }


@app.post("/api/approval-requests/{request_id}/approve")
def decidir_solicitud_aprobacion(
    request_id: int,
    datos: ApprovalDecision,
    api_key_valida: bool = Depends(validar_api_key),
    usuario_actual: User = Depends(
        requiere_rol("juez", "notario", "admin", "admin_ti", "aprobador", "revisor")
    ),
    db: Session = Depends(get_db)
):
    if datos.decision not in {"approved", "rejected", "changes_requested"}:
        raise HTTPException(status_code=422, detail={"error": "Decision invalida"})

    solicitud = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.id == request_id)
        .first()
    )

    if not solicitud:
        raise HTTPException(status_code=404, detail={"error": "Solicitud no encontrada"})

    documento = obtener_documento_autorizado(db, solicitud.document_id, usuario_actual)
    solicitud.status = datos.decision
    solicitud.reviewer_id = usuario_actual.id
    solicitud.comment = datos.comment or solicitud.comment
    solicitud.decided_at = datetime.now(timezone.utc)
    documento.status = "approved" if datos.decision == "approved" else "rejected"

    db.commit()

    return {
        "id": solicitud.id,
        "document_id": solicitud.document_id,
        "status": solicitud.status,
        "reviewer_id": solicitud.reviewer_id,
        "document_status": documento.status
    }


@app.post("/api/documents/{document_id}/signature-requests")
def crear_solicitud_firma(
    document_id: int,
    datos: SignatureRequestCreate,
    api_key_valida: bool = Depends(validar_api_key),
    usuario_actual: User = Depends(
        requiere_rol("juez", "notario", "admin", "admin_ti", "aprobador")
    ),
    db: Session = Depends(get_db)
):
    if datos.mode not in {"sequential", "parallel"}:
        raise HTTPException(status_code=422, detail={"error": "Modo de firma invalido"})

    documento = obtener_documento_autorizado(db, document_id, usuario_actual)

    if documento.status not in {"approved", "signature_pending", "signed"}:
        raise HTTPException(
            status_code=409,
            detail={"error": "El documento debe estar aprobado antes de solicitar firma"}
        )

    solicitud = SignatureRequest(
        document_id=documento.id,
        signer_id=datos.signer_id,
        signing_order=datos.signing_order,
        mode=datos.mode,
        status="pending"
    )
    documento.status = "signature_pending"

    db.add(solicitud)
    db.commit()
    db.refresh(solicitud)

    return {
        "id": solicitud.id,
        "document_id": solicitud.document_id,
        "signer_id": solicitud.signer_id,
        "signing_order": solicitud.signing_order,
        "mode": solicitud.mode,
        "status": solicitud.status
    }


@app.post("/api/signature-requests/{request_id}/sign")
def firmar_documento(
    request_id: int,
    datos: SignatureSign,
    api_key_valida: bool = Depends(validar_api_key),
    usuario_actual: User = Depends(obtener_usuario_actual),
    db: Session = Depends(get_db)
):
    solicitud = (
        db.query(SignatureRequest)
        .filter(SignatureRequest.id == request_id)
        .first()
    )

    if not solicitud:
        raise HTTPException(status_code=404, detail={"error": "Solicitud de firma no encontrada"})

    if solicitud.signer_id != usuario_actual.id and usuario_actual.role.name not in {"admin", "admin_ti", "notario"}:
        raise HTTPException(status_code=403, detail={"error": "No puedes firmar esta solicitud"})

    documento = obtener_documento_autorizado(db, solicitud.document_id, usuario_actual)
    version = (
        db.query(LegalDocumentVersion)
        .filter(
            LegalDocumentVersion.id == datos.document_version_id,
            LegalDocumentVersion.document_id == documento.id
        )
        .first()
    )

    if not version:
        raise HTTPException(status_code=404, detail={"error": "Version de documento no encontrada"})

    evento = SignatureEvent(
        signature_request_id=solicitud.id,
        document_version_id=version.id,
        signer_id=usuario_actual.id,
        signature_hash=datos.signature_hash,
        signed_payload=datos.signed_payload
    )
    solicitud.status = "signed"
    solicitud.signed_at = datetime.now(timezone.utc)

    firmas_pendientes = (
        db.query(SignatureRequest)
        .filter(
            SignatureRequest.document_id == documento.id,
            SignatureRequest.id != solicitud.id,
            SignatureRequest.status == "pending"
        )
        .count()
    )

    if firmas_pendientes == 0:
        documento.status = "signed"

    db.add(evento)
    db.commit()
    db.refresh(evento)

    return {
        "id": evento.id,
        "signature_request_id": solicitud.id,
        "document_id": documento.id,
        "document_status": documento.status,
        "signature_status": solicitud.status,
        "signature_hash": evento.signature_hash
    }
