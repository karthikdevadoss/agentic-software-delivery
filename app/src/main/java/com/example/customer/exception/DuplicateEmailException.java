package com.example.customer.exception;

/** Thrown when Update Email is asked to change a customer's email to one
 * already in use by a DIFFERENT customer -- see GlobalExceptionHandler
 * for why this must surface as a clean 409 rather than an ugly, unguided
 * database-constraint 500 (same reasoning as EnrollmentInProgressException). */
public class DuplicateEmailException extends RuntimeException {

    public DuplicateEmailException(String message) {
        super(message);
    }
}
