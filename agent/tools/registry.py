from dataclasses import dataclass


@dataclass
class DepSource:
    source: str
    changelog: str


def fetch_dep_source(dep: str, version: str) -> str:
    raise NotImplementedError


def fetch_dep_diff(dep: str, old_v: str, new_v: str) -> str:
    raise NotImplementedError


def fetch_migration_guide(dep: str, old_v: str, new_v: str) -> str:
    raise NotImplementedError
