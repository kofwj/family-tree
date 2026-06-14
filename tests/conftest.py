import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def app_module(tmp_path):
    import backend.main as main

    db_path = tmp_path / "family.db"
    data_dir = tmp_path / "data"
    backup_dir = data_dir / "backups"
    photo_dir = data_dir / "member-photos"
    backup_dir.mkdir(parents=True, exist_ok=True)
    photo_dir.mkdir(parents=True, exist_ok=True)

    old_engine = main.engine
    old_database_url = main.DATABASE_URL
    old_data_dir = main.DATA_DIR
    old_backup_dir = main.BACKUP_DIR
    old_photo_dir = main.PHOTO_DIR
    old_jwt_secret = main.JWT_SECRET
    old_admin_password = main.ADMIN_PASSWORD
    old_password_min_length = main.PASSWORD_MIN_LENGTH
    old_excel_max_bytes = main.EXCEL_MAX_BYTES

    main.engine = main.create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    main.DATABASE_URL = f"sqlite:///{db_path}"
    main.DATA_DIR = data_dir
    main.BACKUP_DIR = backup_dir
    main.PHOTO_DIR = photo_dir
    main.JWT_SECRET = "test-secret-with-enough-length-123"
    main.ADMIN_PASSWORD = "TestPass123"
    main.PASSWORD_MIN_LENGTH = 8
    main.LOGIN_ATTEMPTS.clear()
    main.init_db()
    yield main
    main.engine.dispose()
    main.engine = old_engine
    main.DATABASE_URL = old_database_url
    main.DATA_DIR = old_data_dir
    main.BACKUP_DIR = old_backup_dir
    main.PHOTO_DIR = old_photo_dir
    main.JWT_SECRET = old_jwt_secret
    main.ADMIN_PASSWORD = old_admin_password
    main.PASSWORD_MIN_LENGTH = old_password_min_length
    main.EXCEL_MAX_BYTES = old_excel_max_bytes


@pytest.fixture()
def client(app_module):
    return TestClient(app_module.app)
