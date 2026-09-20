package com.example.customer.exception;

/** Thrown when RateLimiterService.allow() rejects a request -- mapped to
 * 429 by GlobalExceptionHandler, never a raw connection-refused/500. */
public class RateLimitExceededException extends RuntimeException {

    public RateLimitExceededException(String message) {
        super(message);
    }
}
