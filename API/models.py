from sqlalchemy import (
    Boolean,
    BigInteger,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
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
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)

    role = relationship(
        "Role",
        back_populates="users"
    )


class LegalCase(Base):
    __tablename__ = "legal_cases"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(180), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        Enum("active", "paused", "concluded", "archived"),
        nullable=False,
        default="active"
    )
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    archived_at = Column(DateTime, nullable=True)

    creator = relationship("User", foreign_keys=[created_by])
    participants = relationship("CaseParticipant", back_populates="case")
    documents = relationship("LegalDocument", back_populates="case")


class CaseParticipant(Base):
    __tablename__ = "case_participants"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("legal_cases.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_name = Column(
        Enum("interesado", "testigo", "abogado", "juez", "notario"),
        nullable=False
    )
    represented_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=True)

    case = relationship("LegalCase", back_populates="participants")
    user = relationship("User", foreign_keys=[user_id])
    represented_user = relationship("User", foreign_keys=[represented_user_id])


class LegalDocumentType(Base):
    __tablename__ = "legal_document_types"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(80), nullable=False, unique=True)
    name = Column(String(150), nullable=False)
    classification = Column(
        Enum(
            "personal_sensitive",
            "witness_id",
            "marriage_certificate",
            "libelo",
            "trial_pdf",
            "other"
        ),
        nullable=False
    )
    allowed_extensions = Column(String(255), nullable=False)
    max_size_mb = Column(Integer, nullable=False, default=25)
    requires_ocr = Column(Boolean, nullable=False, default=False)
    requires_approval = Column(Boolean, nullable=False, default=True)
    requires_signature = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)

    documents = relationship("LegalDocument", back_populates="document_type")


class LegalDocument(Base):
    __tablename__ = "legal_documents"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("legal_cases.id"), nullable=False)
    document_type_id = Column(Integer, ForeignKey("legal_document_types.id"), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(180), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        Enum(
            "draft",
            "uploaded",
            "ocr_pending",
            "under_review",
            "approved",
            "signature_pending",
            "signed",
            "rejected",
            "archived"
        ),
        nullable=False,
        default="draft"
    )
    current_version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    archived_at = Column(DateTime, nullable=True)

    case = relationship("LegalCase", back_populates="documents")
    document_type = relationship("LegalDocumentType", back_populates="documents")
    owner = relationship("User", foreign_keys=[owner_id])
    versions = relationship("LegalDocumentVersion", back_populates="document")


class LegalDocumentVersion(Base):
    __tablename__ = "legal_document_versions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("legal_documents.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    original_name = Column(String(255), nullable=False)
    stored_name = Column(String(255), nullable=False, unique=True)
    storage_path = Column(String(500), nullable=False)
    content_type = Column(String(120), nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    sha256 = Column(String(64), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=True)

    document = relationship("LegalDocument", back_populates="versions")
    uploader = relationship("User", foreign_keys=[uploaded_by])


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("legal_documents.id"), nullable=False)
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(
        Enum("pending", "approved", "rejected", "changes_requested"),
        nullable=False,
        default="pending"
    )
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=True)
    decided_at = Column(DateTime, nullable=True)


class SignatureRequest(Base):
    __tablename__ = "signature_requests"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("legal_documents.id"), nullable=False)
    signer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    signing_order = Column(Integer, nullable=False, default=1)
    mode = Column(Enum("sequential", "parallel"), nullable=False, default="sequential")
    status = Column(
        Enum("pending", "signed", "rejected", "cancelled"),
        nullable=False,
        default="pending"
    )
    created_at = Column(DateTime, nullable=True)
    signed_at = Column(DateTime, nullable=True)


class SignatureEvent(Base):
    __tablename__ = "signature_events"

    id = Column(Integer, primary_key=True, index=True)
    signature_request_id = Column(Integer, ForeignKey("signature_requests.id"), nullable=False)
    document_version_id = Column(Integer, ForeignKey("legal_document_versions.id"), nullable=False)
    signer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    signature_hash = Column(String(128), nullable=False)
    signed_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=True)


class DocumentAccessEvent(Base):
    __tablename__ = "document_access_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    document_id = Column(Integer, ForeignKey("legal_documents.id"), nullable=False)
    action = Column(
        Enum("view", "upload", "approve", "sign", "download", "archive", "restore"),
        nullable=False
    )
    channel = Column(Enum("web", "mobile", "api"), nullable=False)
    allowed = Column(Boolean, nullable=False)
    reason = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=True)
