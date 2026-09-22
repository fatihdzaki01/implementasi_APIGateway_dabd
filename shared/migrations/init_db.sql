-- ============================================================
-- DDL Script — buat semua tabel sekaligus
-- Jalankan: psql -U user -d gateway_db -f shared/migrations/init_db.sql
-- Atau dari Python: python -c "from shared.db import init_db; init_db()"
-- ============================================================

-- Tabel: roles
CREATE TABLE IF NOT EXISTS roles (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(50) UNIQUE NOT NULL,
    permissions JSONB DEFAULT '{}',
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Seed roles default
INSERT INTO roles (name, permissions) VALUES
    ('admin',    '{"* *": true, "all": true}'),
    ('user',     '{"GET /service-a/*": true, "GET /service-b/*": true, "GET /service-c/*": true, "POST /service-a/*": true, "POST /service-b/*": true, "POST /service-c/*": true, "POST /service-a/items": true, "POST /service-b/products": true, "POST /service-c/users": true}'),
    ('readonly', '{"GET *": true, "GET": true, "HEAD *": true}')
ON CONFLICT (name) DO UPDATE SET permissions = EXCLUDED.permissions;

-- Tabel: users
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(100) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role_id       INT REFERENCES roles(id),
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- Tabel: api_keys
CREATE TABLE IF NOT EXISTS api_keys (
    id          SERIAL PRIMARY KEY,
    key_hash    TEXT UNIQUE NOT NULL,
    user_id     INT REFERENCES users(id) NOT NULL,
    description VARCHAR(255),
    is_active   BOOLEAN DEFAULT TRUE,
    expires_at  TIMESTAMP,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Tabel: request_logs
CREATE TABLE IF NOT EXISTS request_logs (
    id               SERIAL PRIMARY KEY,
    request_id       VARCHAR(36) NOT NULL,
    timestamp        TIMESTAMP NOT NULL DEFAULT NOW(),
    method           VARCHAR(10) NOT NULL,
    path             TEXT NOT NULL,
    target_service   VARCHAR(100),
    status_code      INT,
    response_time_ms FLOAT,
    user_id          INT REFERENCES users(id),
    ip_address       VARCHAR(50),

    -- index untuk query log by request_id dan timestamp
    CONSTRAINT uq_request_id UNIQUE (request_id)
);

CREATE INDEX IF NOT EXISTS idx_request_logs_timestamp ON request_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_request_logs_target_service ON request_logs(target_service);
CREATE INDEX IF NOT EXISTS idx_request_logs_status_code ON request_logs(status_code);
