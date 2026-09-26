"""The application-level contract behind the individual subsystem installers."""

from dataclasses import dataclass

import pytest

from sillo import SilloApp


@dataclass
class ExampleInstallable:
    name: str = "example"
    source: str = "example"
    calls: int = 0

    def install(self, app: SilloApp) -> dict[str, str]:
        self.calls += 1
        service = {"source": self.source}
        app.state[self.name] = service
        return service


def test_install_wires_a_named_service_once():
    app = SilloApp()
    installable = ExampleInstallable()

    service = app.install(installable)

    assert service == {"source": "example"}
    assert app.state["example"] is service
    assert app.installations == {"example": service}
    assert app.install(installable) is service
    assert installable.calls == 1


def test_first_installation_wins_when_another_instance_has_the_same_name():
    app = SilloApp()
    first = ExampleInstallable(source="first")
    second = ExampleInstallable(source="second")

    service = app.install(first)

    assert app.install(second) is service
    assert service == {"source": "first"}
    assert first.calls == 1
    assert second.calls == 0


class FailingInstallable:
    name = "retryable"

    def install(self, app: SilloApp) -> object:
        raise RuntimeError("connection unavailable")


def test_failed_installation_does_not_poison_a_name():
    app = SilloApp()

    with pytest.raises(RuntimeError, match="connection unavailable"):
        app.install(FailingInstallable())

    assert "retryable" not in app.installations
    assert app.install(ExampleInstallable(name="retryable")) == {"source": "example"}


def test_installations_cannot_be_mutated_from_the_outside():
    app = SilloApp()
    app.install(ExampleInstallable())

    with pytest.raises(TypeError):
        app.installations["other"] = object()  # type: ignore[index]


@pytest.mark.parametrize("name", ["", None, 42])
def test_install_requires_a_non_empty_string_name(name):
    app = SilloApp()
    installable = ExampleInstallable(name=name)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="non-empty string"):
        app.install(installable)
