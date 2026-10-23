"""Manual dependency injection container."""

from dataclasses import dataclass

from domain_app.models import Vehicle
from domain_app.notifiers import ConsoleNotifier
from domain_app.protocols import Notifier, Repository
from domain_app.repositories import InMemoryRepository
from domain_app.services import CatalogService


@dataclass
class Container:
    """Holds the wired objects of the application."""

    repository: Repository[Vehicle]
    notifier: Notifier
    service: CatalogService


def build_container(
    repository: Repository[Vehicle] | None = None,
    notifier: Notifier | None = None,
) -> Container:
    """Compose the application; any dependency can be replaced."""
    repo: Repository[Vehicle] = (
        repository if repository is not None else InMemoryRepository[Vehicle]()
    )
    sink: Notifier = notifier if notifier is not None else ConsoleNotifier()
    return Container(repo, sink, CatalogService(repo, sink))
