"""Reporting service: read-only queries over the Singleton history log.

The domain Singleton OrderHistoryLog is realised as the
SqlAlchemyHistoryRepository, whose ITERATOR (`iter(repo)`) and aggregate
queries power every figure shown on the manager report.
"""
from datetime import datetime, timedelta

from app.infra.repositories import SqlAlchemyHistoryRepository


def _repo(db):
    return SqlAlchemyHistoryRepository(db)


def records(db):
    return list(iter(_repo(db)))


def top_items(db, n=5):
    return _repo(db).top_items(n)


def revenue(db):
    return _repo(db).total_revenue()


def most_frequent(db):
    return _repo(db).most_frequent_item()


def for_table(db, table_no):
    return _repo(db).for_table(table_no)


def last_24h(db):
    now = datetime.now()
    return len(_repo(db).in_range(now - timedelta(days=1), now))


def summary(db):
    repo = _repo(db)
    return {
        "records": list(iter(repo)),
        "top_items": top_items(db),
        "revenue": revenue(db),
        "most_frequent": most_frequent(db),
        "last_24h": last_24h(db),
        "count": len(repo),
    }
