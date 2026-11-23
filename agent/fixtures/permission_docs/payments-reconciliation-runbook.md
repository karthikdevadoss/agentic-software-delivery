# FIXTURE (fake stand-in for a Notion page) -- Payments reconciliation job runbook

This is invented test data. It is not a real Notion export and describes no real system.

## Nightly reconciliation job failure
If the nightly payments reconciliation job fails, page the on-call engineer, then rerun the ledger reconciliation batch with the --repair flag. The ledger repair credentials live in the fictional vault path vault://fixture/ledger-repair.

## Rollback of a bad reconciliation batch
Rollback of a bad reconciliation batch requires two engineers to approve the ledger repair rollback.
