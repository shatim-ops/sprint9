import os

# issuer в токене тот, по которому в Keycloak ходит браузер (localhost:8080),
# а ключи сервис забирает по внутреннему адресу из docker-сети.
KEYCLOAK_ISSUER = os.getenv("KEYCLOAK_ISSUER", "http://localhost:8080/realms/reports-realm")
KEYCLOAK_JWKS_URL = os.getenv(
    "KEYCLOAK_JWKS_URL",
    "http://keycloak:8080/realms/reports-realm/protocol/openid-connect/certs",
)
ALLOWED_CLIENTS = os.getenv("ALLOWED_CLIENTS", "reports-frontend").split(",")
REPORTS_ROLE = os.getenv("REPORTS_ROLE", "prothetic_user")

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "reports_api")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DB = os.getenv("CLICKHOUSE_DB", "reports")

# если период не задан, отдаём последние N обработанных дней
DEFAULT_PERIOD_DAYS = int(os.getenv("DEFAULT_PERIOD_DAYS", "7"))
MAX_PERIOD_DAYS = int(os.getenv("MAX_PERIOD_DAYS", "366"))
