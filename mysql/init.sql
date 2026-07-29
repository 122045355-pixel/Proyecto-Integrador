CREATE DATABASE IF NOT EXISTS gestion_documental
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE gestion_documental;

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS refresh_tokens;
DROP TABLE IF EXISTS reviews;
DROP TABLE IF EXISTS workflow_steps;
DROP TABLE IF EXISTS document_versions;
DROP TABLE IF EXISTS documents;
DROP TABLE IF EXISTS project_document_requirements;
DROP TABLE IF EXISTS document_types;
DROP TABLE IF EXISTS project_members;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS team_members;
DROP TABLE IF EXISTS teams;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS roles;

SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role_id INT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (role_id)
        REFERENCES roles(id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

CREATE TABLE teams (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE team_members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    team_id INT NOT NULL,
    user_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(team_id, user_id),

    FOREIGN KEY (team_id)
        REFERENCES teams(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

CREATE TABLE projects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(180) NOT NULL,
    description TEXT,
    status ENUM(
        'draft',
        'pending_documents',
        'under_review',
        'approved',
        'rejected',
        'cancelled'
    ) NOT NULL DEFAULT 'draft',
    owner_id INT NOT NULL,
    team_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    submitted_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,

    FOREIGN KEY (owner_id)
        REFERENCES users(id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

    FOREIGN KEY (team_id)
        REFERENCES teams(id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

CREATE TABLE project_members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    user_id INT NOT NULL,
    responsibility VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(project_id, user_id),

    FOREIGN KEY (project_id)
        REFERENCES projects(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

CREATE TABLE document_types (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL UNIQUE,
    description TEXT,
    allowed_extensions VARCHAR(255),
    max_size_mb INT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE project_document_requirements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    document_type_id INT NOT NULL,
    responsible_user_id INT NOT NULL,
    is_required BOOLEAN NOT NULL DEFAULT TRUE,
    status ENUM(
        'pending',
        'uploaded',
        'under_review',
        'approved',
        'rejected'
    ) NOT NULL DEFAULT 'pending',
    due_date DATE NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (project_id)
        REFERENCES projects(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    FOREIGN KEY (document_type_id)
        REFERENCES document_types(id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

    FOREIGN KEY (responsible_user_id)
        REFERENCES users(id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

CREATE TABLE documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    requirement_id INT NULL,
    document_type_id INT NOT NULL,
    owner_id INT NOT NULL,
    title VARCHAR(180) NOT NULL,
    description TEXT,
    status ENUM(
        'draft',
        'uploaded',
        'under_review',
        'approved',
        'rejected'
    ) NOT NULL DEFAULT 'draft',
    current_version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (project_id)
        REFERENCES projects(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    FOREIGN KEY (requirement_id)
        REFERENCES project_document_requirements(id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,

    FOREIGN KEY (document_type_id)
        REFERENCES document_types(id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

    FOREIGN KEY (owner_id)
        REFERENCES users(id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

CREATE TABLE document_versions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id INT NOT NULL,
    version_number INT NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    stored_name VARCHAR(255) NOT NULL UNIQUE,
    storage_path VARCHAR(500) NOT NULL,
    content_type VARCHAR(120),
    size_bytes BIGINT,
    sha256 VARCHAR(64),
    uploaded_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(document_id, version_number),

    FOREIGN KEY (document_id)
        REFERENCES documents(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    FOREIGN KEY (uploaded_by)
        REFERENCES users(id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

CREATE TABLE workflow_steps (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    name VARCHAR(150) NOT NULL,
    step_order INT NOT NULL,
    required_role_id INT NOT NULL,
    assigned_user_id INT NULL,
    status ENUM(
        'pending',
        'in_progress',
        'approved',
        'rejected'
    ) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(project_id, step_order),

    FOREIGN KEY (project_id)
        REFERENCES projects(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    FOREIGN KEY (required_role_id)
        REFERENCES roles(id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

    FOREIGN KEY (assigned_user_id)
        REFERENCES users(id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
);

CREATE TABLE reviews (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    document_id INT NULL,
    workflow_step_id INT NOT NULL,
    reviewer_id INT NOT NULL,
    decision ENUM(
        'approved',
        'rejected',
        'changes_requested'
    ) NOT NULL,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (project_id)
        REFERENCES projects(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    FOREIGN KEY (document_id)
        REFERENCES documents(id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,

    FOREIGN KEY (workflow_step_id)
        REFERENCES workflow_steps(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    FOREIGN KEY (reviewer_id)
        REFERENCES users(id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

CREATE TABLE refresh_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

CREATE TABLE audit_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    action VARCHAR(80) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id INT NOT NULL,
    details JSON,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
);

INSERT INTO roles (name, description) VALUES
('usuario', 'Usuario general de la aplicación'),
('revisor', 'Usuario encargado de revisar documentos'),
('aprobador', 'Usuario encargado de aprobar proyectos'),
('admin', 'Administrador del sistema');

INSERT INTO teams (name, description) VALUES
('Legal', 'Área legal y de cumplimiento'),
('Ventas', 'Área comercial'),
('Operaciones', 'Área de operaciones');

INSERT INTO document_types (
    name,
    description,
    allowed_extensions,
    max_size_mb,
    is_active
) VALUES
(
    'Identificación',
    'Documento oficial de identificación',
    'pdf,jpg,jpeg,png',
    10,
    TRUE
),
(
    'Contrato',
    'Contrato relacionado con el proyecto',
    'pdf,doc,docx',
    25,
    TRUE
),
(
    'Comprobante',
    'Comprobante relacionado con el proyecto',
    'pdf,jpg,jpeg,png',
    10,
    TRUE
),
(
    'Dictamen',
    'Dictamen técnico o jurídico',
    'pdf,doc,docx',
    25,
    TRUE
);