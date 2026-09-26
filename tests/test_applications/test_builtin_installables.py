"""Built-in installables share one application-level installation path."""

from sillo import SilloApp
from sillo.mail import Mail, MailConfig
from sillo.record import DatabaseConfig, Record
from sillo.storage import StorageConfig, StorageInstallable
from sillo.work import Work
from sillo.work.scheduler import Scheduler


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
