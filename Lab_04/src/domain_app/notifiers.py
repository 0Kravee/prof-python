"""Concrete implementations of the Notifier protocol."""


class ConsoleNotifier:
    """Prints notifications to the console."""

    def notify(self, message: str) -> None:
        print(f"[notify] {message}")


class InMemoryNotifier:
    """Collects notifications in a list (handy for tests)."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def notify(self, message: str) -> None:
        self.messages.append(message)
