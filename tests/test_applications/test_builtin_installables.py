"""Built-in installables share one application-level installation path."""

from sillo import SilloApp
from sillo.mail import Mail, MailConfig, setup_mail
from sillo.record import DatabaseConfig, Record, setup_record
from sillo.storage import StorageConfig, StorageInstallable, setup_storage
from sillo.work import Work, setup_work
from sillo.work.scheduler import Scheduler, setup_scheduler


def test_builtin_installables_are_visible_in_one_bootstrap_registry():
    app = SilloApp()

    record = app.install(Record(DatabaseConfig(url="sqlite://:memory:")))
    mail = app.install(Mail(MailConfig(suppress_send=True)))
    storage = app.install(StorageInstallable(StorageConfig()))
    work = app.install(Work())

    assert app.installations == {
        "record": record,
        "mail": mail,
        "storage": storage,
        "work": work,
    }
    assert app.state["record"] is record
    assert app.state["mail_client"] is mail
    assert app.state["storage"] is storage
    assert app.state["work"] is work


def test_scheduler_installable_reuses_work_scheduler():
    app = SilloApp()
    work = app.install(Work())

    scheduler = app.install(Scheduler())

    assert scheduler is work["scheduler"]
    assert app.installations["scheduler"] is scheduler


def test_legacy_setup_helpers_register_the_same_installations():
    """Existing bootstraps gain the registry without changing their code."""

    app = SilloApp()

    setup_record(app, DatabaseConfig(url="sqlite://:memory:"))
    setup_mail(app, MailConfig(suppress_send=True))
    setup_storage(app, StorageConfig())
    work = setup_work(app)
    scheduler = setup_scheduler(app)

    assert set(app.installations) == {
        "record",
        "mail",
        "storage",
        "work",
        "scheduler",
    }
    assert scheduler is work["scheduler"]
