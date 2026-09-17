-- Упрощённая модель CRM: клиенты и выданные им протезы.
-- login совпадает с username в Keycloak, по нему сервис отчётов
-- связывает токен с данными клиента.

CREATE TABLE customers (
    id          SERIAL PRIMARY KEY,
    login       VARCHAR(64)  NOT NULL UNIQUE,
    full_name   VARCHAR(200) NOT NULL,
    email       VARCHAR(200) NOT NULL,
    phone       VARCHAR(32),
    birth_date  DATE,
    country     CHAR(2)      NOT NULL DEFAULT 'RU',
    created_at  TIMESTAMP    NOT NULL DEFAULT now(),
    updated_at  TIMESTAMP    NOT NULL DEFAULT now()
);

CREATE TABLE prostheses (
    id             SERIAL PRIMARY KEY,
    customer_id    INTEGER     NOT NULL REFERENCES customers (id),
    serial_number  VARCHAR(32) NOT NULL UNIQUE,
    model          VARCHAR(64) NOT NULL,
    side           VARCHAR(8)  NOT NULL CHECK (side IN ('left', 'right')),
    issued_at      DATE        NOT NULL,
    status         VARCHAR(16) NOT NULL DEFAULT 'active',
    updated_at     TIMESTAMP   NOT NULL DEFAULT now()
);

INSERT INTO customers (login, full_name, email, phone, birth_date, country) VALUES
    ('prothetic1', 'Prothetic One',   'prothetic1@example.com', '+79990000001', '1985-03-14', 'RU'),
    ('prothetic2', 'Prothetic Two',   'prothetic2@example.com', '+79990000002', '1992-11-02', 'RU'),
    ('prothetic3', 'Prothetic Three', 'prothetic3@example.com', '+79990000003', '1978-07-21', 'RU'),
    ('offline_client', 'Клиент без учётки в приложении', 'offline@example.com', NULL, '1969-01-30', 'RU');

-- у первого клиента два протеза, в отчёте они идут отдельными блоками
INSERT INTO prostheses (customer_id, serial_number, model, side, issued_at) VALUES
    (1, 'BP-H2-000101', 'BionicHand 2',    'right', '2025-11-20'),
    (1, 'BP-H1-000057', 'BionicHand 1',    'left',  '2024-06-03'),
    (2, 'BP-H2-000144', 'BionicHand 2',    'left',  '2026-02-11'),
    (3, 'BP-F1-000012', 'BionicForearm 1', 'right', '2026-04-27'),
    (4, 'BP-H1-000031', 'BionicHand 1',    'right', '2023-12-15');
