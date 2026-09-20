package com.example.billingservice.exception;

/**
 * Thrown when BillingCustomerClient could not get a real answer from
 * customer-service (see CustomerLookupOutcome.SERVICE_UNAVAILABLE) --
 * distinct from a genuine "customer not found" (NoSuchElementException,
 * -&gt; 404): this means billing-service's own dependency is unreachable,
 * not that the customer doesn't exist. See GlobalExceptionHandler for the
 * HTTP status mapping and why.
 */
public class CustomerServiceUnavailableException extends RuntimeException {

    public CustomerServiceUnavailableException(String message) {
        super(message);
    }
}
