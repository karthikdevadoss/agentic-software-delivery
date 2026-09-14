package com.example.customer.exception;

/**
 * Thrown by DemoLoginController for an unknown username, wrong password,
 * or a disabled identity -- deliberately NOT a Spring Security
 * AuthenticationException subtype. That distinction matters: an
 * AuthenticationException thrown from application code is intercepted by
 * Spring Security's own ExceptionTranslationFilter before it ever reaches
 * GlobalExceptionHandler, which would silently replace this exception's
 * specific "invalid username or password" message with the generic
 * unauthenticated-request message SecurityConfig's entry point returns
 * for a genuinely missing/invalid bearer token -- a different, real
 * condition from "this login attempt's credentials were wrong."
 */
public class InvalidCredentialsException extends RuntimeException {
    public InvalidCredentialsException(String message) {
        super(message);
    }
}
