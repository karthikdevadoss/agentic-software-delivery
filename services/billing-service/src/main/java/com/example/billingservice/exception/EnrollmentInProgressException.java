package com.example.billingservice.exception;

/** Thrown when a second enrollment request for the same customer arrives
 * while a first one is still in flight -- see EnrollmentLockService's
 * Javadoc for why this is a real correctness concern, not a decorative
 * check, and GlobalExceptionHandler for why this must surface as a clean
 * 409 rather than an ugly, unguided database-constraint 500. Ported
 * unchanged from app/'s com.example.customer.exception.EnrollmentInProgressException. */
public class EnrollmentInProgressException extends RuntimeException {

    public EnrollmentInProgressException(String message) {
        super(message);
    }
}
