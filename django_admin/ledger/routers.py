class LedgerRouter:
    """Ledger models live on the 'ledger' alias; everything else on default.
    Writes to the ledger alias and migrations there are refused."""

    def db_for_read(self, model, **hints):
        return "ledger" if model._meta.app_label == "ledger" else None

    def db_for_write(self, model, **hints):
        return "ledger" if model._meta.app_label == "ledger" else None

    def allow_relation(self, a, b, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == "ledger" or db == "ledger":
            return False
        return None
