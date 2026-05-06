from dataclasses import dataclass
from typing import Callable
from api.settings import settings


@dataclass
class Backends:
    sandbox: str
    github: str
    registry: str


def get_backends() -> Backends:
    return Backends(
        sandbox=settings.sandbox_backend,
        github="github_app",
        registry="pypi",
    )
