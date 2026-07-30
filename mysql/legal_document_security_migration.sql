USE gestion_documental;

INSERT INTO roles (name, description) VALUES
('interesado', 'Parte o interesado con acceso a documentos propios'),
('testigo', 'Testigo con acceso a identificacion y libelos propios'),
('abogado', 'Abogado con acceso a libelos de sus clientes'),
('juez', 'Juez con acceso a casos activos y descarga web autorizada'),
('notario', 'Rol con mayor privilegio documental y descarga web'),
('admin_ti', 'Administrador tecnico del sistema')
ON DUPLICATE KEY UPDATE description = VALUES(description);

CREATE TABLE IF NOT EXISTS legal_cases (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(180) NOT NULL,
    description TEXT,
    status ENUM('active', 'paused', 'concluded', 'archived') NOT NULL DEFAULT 'active',
    created_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    archived_at TIMESTAMP NULL,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS case_participants (
    id INT AUTO_INCREMENT PRIMARY KEY,
    case_id INT NOT NULL,
    user_id INT NOT NULL,
    role_name ENUM('interesado', 'testigo', 'abogado', 'juez', 'notario') NOT NULL,
    represented_user_id INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(case_id, user_id, role_name),
    FOREIGN KEY (case_id) REFERENCES legal_cases(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (represented_user_id) REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS legal_document_types (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(80) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    classification ENUM(
        'personal_sensitive',
        'witness_id',
        'marriage_certificate',
        'libelo',
        'trial_pdf',
        'other'
    ) NOT NULL,
    allowed_extensions VARCHAR(255) NOT NULL,
    max_size_mb INT NOT NULL DEFAULT 25,
    requires_ocr BOOLEAN NOT NULL DEFAULT FALSE,
    requires_approval BOOLEAN NOT NULL DEFAULT TRUE,
    requires_signature BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS legal_documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    case_id INT NOT NULL,
    document_type_id INT NOT NULL,
    owner_id INT NOT NULL,
    title VARCHAR(180) NOT NULL,
    description TEXT,
    status ENUM(
        'draft',
        'uploaded',
        'ocr_pending',
        'under_review',
        'approved',
        'signature_pending',
        'signed',
        'rejected',
        'archived'
    ) NOT NULL DEFAULT 'draft',
    current_version INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    archived_at TIMESTAMP NULL,
    FOREIGN KEY (case_id) REFERENCES legal_cases(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (document_type_id) REFERENCES legal_document_types(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS legal_document_versions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id INT NOT NULL,
    version_number INT NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    stored_name VARCHAR(255) NOT NULL UNIQUE,
    storage_path VARCHAR(500) NOT NULL,
    content_type VARCHAR(120),
    size_bytes BIGINT,
    sha256 VARCHAR(64) NOT NULL,
    uploaded_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, version_number),
    FOREIGN KEY (document_id) REFERENCES legal_documents(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS ocr_jobs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_version_id INT NOT NULL,
    status ENUM('pending', 'processing', 'completed', 'failed') NOT NULL DEFAULT 'pending',
    provider VARCHAR(80),
    extracted_text LONGTEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    FOREIGN KEY (document_version_id) REFERENCES legal_document_versions(id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS approval_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id INT NOT NULL,
    requested_by INT NOT NULL,
    reviewer_id INT NULL,
    status ENUM('pending', 'approved', 'rejected', 'changes_requested') NOT NULL DEFAULT 'pending',
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    decided_at TIMESTAMP NULL,
    FOREIGN KEY (document_id) REFERENCES legal_documents(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (requested_by) REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (reviewer_id) REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS signature_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id INT NOT NULL,
    signer_id INT NOT NULL,
    signing_order INT NOT NULL DEFAULT 1,
    mode ENUM('sequential', 'parallel') NOT NULL DEFAULT 'sequential',
    status ENUM('pending', 'signed', 'rejected', 'cancelled') NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    signed_at TIMESTAMP NULL,
    FOREIGN KEY (document_id) REFERENCES legal_documents(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (signer_id) REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS signature_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    signature_request_id INT NOT NULL,
    document_version_id INT NOT NULL,
    signer_id INT NOT NULL,
    signature_hash VARCHAR(128) NOT NULL,
    signed_payload JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (signature_request_id) REFERENCES signature_requests(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (document_version_id) REFERENCES legal_document_versions(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (signer_id) REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS archive_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    case_id INT NOT NULL,
    archive_path VARCHAR(500) NOT NULL,
    sha256 VARCHAR(64),
    created_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    restored_at TIMESTAMP NULL,
    FOREIGN KEY (case_id) REFERENCES legal_cases(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE IF NOT EXISTS document_access_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    document_id INT NOT NULL,
    action ENUM('view', 'upload', 'approve', 'sign', 'download', 'archive', 'restore') NOT NULL,
    channel ENUM('web', 'mobile', 'api') NOT NULL,
    allowed BOOLEAN NOT NULL,
    reason VARCHAR(255),
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (document_id) REFERENCES legal_documents(id) ON DELETE RESTRICT ON UPDATE CASCADE
);
