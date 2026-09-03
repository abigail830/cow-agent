from app.db.readonly_sql import _postgres_has_config, _postgres_ssl_mode


def test_postgres_has_config_accepts_database_url():
    assert _postgres_has_config({"DATABASE_URL": "postgresql://u:p@h/db"})


def test_postgres_has_config_accepts_split_env():
    assert _postgres_has_config({"DB_HOST": "db.example.com", "DB_USER": "reader"})


def test_postgres_has_config_rejects_empty():
    assert not _postgres_has_config({})
    assert not _postgres_has_config({"DATABASE_URL": "  "})


def test_postgres_ssl_mode_for_azure_host():
    assert _postgres_ssl_mode({}, "smart-sales-pg-prod-sea.postgres.database.azure.com") == "require"


def test_postgres_ssl_mode_explicit_disable():
    assert _postgres_ssl_mode({"DB_SSL_MODE": "disable"}, "localhost") is False
