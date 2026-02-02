import pytest
import asyncio
from uuid import uuid4

from api.admin import create_admin, reset_admin_password, delete_admin, list_admins
from api.models import AuditLog
from auth.models import AdminUser


class DummyResult:
    def __init__(self, obj):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class DummySession:
    def __init__(self, obj=None):
        # obj used for select returns (scalar_one_or_none)
        self.obj = obj
        self.added = []
        self.executed = []

    async def execute(self, query):
        # Very simple behavior: if query contains 'WHERE admin_user.email' and we have obj, return it
        self.executed.append(query)
        return DummyResult(self.obj)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass


class DummyAdmin:
    def __init__(self):
        self.id = 'admin-id'
        self.email = 'admin@example.com'


@pytest.mark.asyncio
async def test_create_admin_adds_user_and_audit():
    # No existing user
    db = DummySession(obj=None)
    req = type('R', (), {'email': 'newadmin@example.com', 'password': 'S3cure!', 'role': 'admin'})()
    admin = DummyAdmin()

    res = await create_admin(req, admin=admin, db=db)

    # Should add an AdminUser and an AuditLog to session
    assert any(isinstance(x, AdminUser) for x in db.added)
    assert any(isinstance(x, AuditLog) for x in db.added)
    assert res['message'] == 'admin_created'


@pytest.mark.asyncio
async def test_reset_admin_password_changes_hash_and_audit():
    # Existing user
    existing = AdminUser(email='exists@example.com', hashed_password='old', role='admin')
    db = DummySession(obj=existing)
    req = type('R', (), {'email': 'exists@example.com', 'password': 'N3wP@ss!'})()
    admin = DummyAdmin()

    res = await reset_admin_password(req, admin=admin, db=db)

    # Check hashed password updated
    assert existing.hashed_password != 'old'
    assert any(isinstance(x, AuditLog) for x in db.added)
    assert res['message'] == 'password_reset'


@pytest.mark.asyncio
async def test_delete_admin_deactivates_and_audits():
    existing = AdminUser(email='del@example.com', hashed_password='x', role='admin')
    db = DummySession(obj=existing)
    req = type('R', (), {'email': 'del@example.com', 'hard': False})()
    admin = DummyAdmin()

    res = await delete_admin(req, admin=admin, db=db)

    assert any(isinstance(x, AuditLog) for x in db.added)
    assert res['message'] == 'deactivate_admin'
