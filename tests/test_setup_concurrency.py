from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import select,func


def test_first_admin_is_claimed_once_under_concurrent_setup(tmp_path,monkeypatch):
    from server.app import create_app
    from server import auth
    from server.db import User
    app=create_app(database_url=f'sqlite:///{tmp_path / "setup.db"}',storage_dir=tmp_path/'files',testing=True)
    original=auth.password_hash;barrier=Barrier(2)
    def hash_after_both_checks(password):
        barrier.wait(timeout=5)
        return original(password)
    monkeypatch.setattr(auth,'password_hash',hash_after_both_checks)
    with TestClient(app) as client:
        def setup(i):
            return client.post('/api/auth/setup',json={'username':f'owner{i}','password':'SetupTest!2026'}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(setup,[1,2]))
        assert sorted(results)==[201,409]
        with app.state.sessions() as db:assert db.scalar(select(func.count()).select_from(User))==1
