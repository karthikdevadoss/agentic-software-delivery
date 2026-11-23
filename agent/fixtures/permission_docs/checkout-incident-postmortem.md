# FIXTURE (fake stand-in for a Slack-thread export) -- Checkout outage postmortem

This is invented test data. It is not a real Slack export and describes no real incident.

## Root cause
The fictional checkout outage was caused by an exhausted database connection pool after a retry storm in the cart service.

## Follow-ups
Add a circuit breaker to the cart service retry path and alert on connection pool saturation.
