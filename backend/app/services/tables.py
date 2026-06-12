"""Table service: drive the domain STATE pattern over persisted TableRows.

Each mutating call loads the row, rebuilds the domain Table (TableRepo.to_domain),
applies the transition, persists the new label and commits. IllegalStateTransition
bubbles up so the router can map it to a flash.
"""
from app.infra.repositories import TableRepo


def list_tables(db):
    return TableRepo(db).list_all()


def seat(db, number):
    repo = TableRepo(db)
    row = repo.get(number)
    table = repo.to_domain(row)
    table.advance()
    repo.save_state(number, table.status())
    db.commit()
    return repo.get(number)


def reserve(db, number):
    repo = TableRepo(db)
    row = repo.get(number)
    table = repo.to_domain(row)
    table.reserve()
    repo.save_state(number, table.status())
    db.commit()
    return repo.get(number)


def advance(db, number):
    repo = TableRepo(db)
    row = repo.get(number)
    table = repo.to_domain(row)
    table.advance()
    repo.save_state(number, table.status())
    db.commit()
    return repo.get(number)
