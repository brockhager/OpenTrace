import pytest
import asyncio
from uuid import uuid4

from api.person import update_person, PersonUpdateRequest
from api.models import AuditLog


class DummyPerson:
    def __init__(self, pfif_id, is_confirmed=False):
        self.pfif_id = pfif_id
        self.is_confirmed = is_confirmed
        self.id = uuid4()


class DummyResult:
    def __init__(self, obj):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class DummySession:
    def __init__(self, obj):
        self.obj = obj
        self.added = []

    async def execute(self, query):
        return DummyResult(self.obj)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        # no-op for test
        pass


class DummyAdmin:
    def __init__(self, email='admin@example.com'):
        self.email = email


@pytest.mark.asyncio
async def test_update_person_creates_audit_log_on_confirm_change():
    person = DummyPerson('opentrace.org/person.manual.PER-TEST', is_confirmed=False)
    db = DummySession(person)
    admin = DummyAdmin('mod@example.com')

    # Toggle confirmation to True
    req = PersonUpdateRequest(is_confirmed=True)
    res = await update_person(person.pfif_id, req, db=db, admin=admin)

    # Person object should be updated
    assert person.is_confirmed is True

    # An audit log entry should be added to the session
    assert any(isinstance(x, AuditLog) for x in db.added)
    audit = next(x for x in db.added if isinstance(x, AuditLog))
    assert audit.action == 'person_confirmation_changed'
    assert audit.actor_id == 'mod@example.com'
    assert audit.details['old_is_confirmed'] is False
    assert audit.details['new_is_confirmed'] is True
    assert audit.details['pfif_id'] == person.pfif_id


@pytest.mark.asyncio
async def test_update_person_no_audit_if_no_change():
    person = DummyPerson('opentrace.org/person.manual.PER-NOCHANGE', is_confirmed=True)
    db = DummySession(person)
    admin = DummyAdmin('mod2@example.com')

    # Request doesn't change is_confirmed
    req = PersonUpdateRequest(family_name='Smith')
    res = await update_person(person.pfif_id, req, db=db, admin=admin)

    # No audit entries added
    assert not any(isinstance(x, AuditLog) for x in db.added)
