package com.example.customer.exception;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.NoSuchElementException;

/**
 * Single, centralized place for turning exceptions into HTTP responses —
 * previously this was one inline @ExceptionHandler method on
 * CustomerController, which does not scale past one exception type and
 * mixes routing concerns with error-shaping concerns. Every error
 * response is now structured JSON (an "error" field, and a per-field
 * "errors" map for validation failures) instead of a raw plain-text
 * string body.
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(NoSuchElementException.class)
    public ResponseEntity<Map<String, String>> handleNotFound(NoSuchElementException ex) {
        Map<String, String> body = new LinkedHashMap<>();
        body.put("error", ex.getMessage());
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(body);
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> handleValidationFailure(MethodArgumentNotValidException ex) {
        Map<String, String> fieldErrors = new LinkedHashMap<>();
        for (FieldError fieldError : ex.getBindingResult().getFieldErrors()) {
            fieldErrors.put(fieldError.getField(), fieldError.getDefaultMessage());
        }
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("error", "validation failed");
        body.put("fieldErrors", fieldErrors);
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(body);
    }

    /** General-purpose 400 for a plain request-level validation failure
     * that isn't Bean-Validation-annotation-driven (e.g. AppointmentController's
     * past-date rejection) -- reusable beyond just that one case. */
    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, String>> handleBadRequest(IllegalArgumentException ex) {
        Map<String, String> body = new LinkedHashMap<>();
        body.put("error", ex.getMessage());
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(body);
    }

    /** 403 for an authenticated, correctly-scoped USER-persona token that
     * requested a customer outside its own bound workspace -- distinct
     * from Spring Security's own insufficient_scope 403. */
    @ExceptionHandler(ForbiddenWorkspaceAccessException.class)
    public ResponseEntity<Map<String, String>> handleForbiddenWorkspace(ForbiddenWorkspaceAccessException ex) {
        Map<String, String> body = new LinkedHashMap<>();
        body.put("error", ex.getMessage());
        return ResponseEntity.status(HttpStatus.FORBIDDEN).body(body);
    }

    /** 401 for /auth/login with an unknown username, wrong password, or a
     * disabled identity -- always the same generic message, deliberately
     * never revealing which part was wrong. */
    @ExceptionHandler(InvalidCredentialsException.class)
    public ResponseEntity<Map<String, String>> handleInvalidCredentials(InvalidCredentialsException ex) {
        Map<String, String> body = new LinkedHashMap<>();
        body.put("error", ex.getMessage());
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(body);
    }

    /** 409 for a real concurrent-enrollment collision (see
     * EnrollmentLockService) -- a clean, actionable "retry" signal instead
     * of the raw 500 a caller would otherwise see if two requests both
     * reached the database's partial-unique-index safety net at once. */
    @ExceptionHandler(EnrollmentInProgressException.class)
    public ResponseEntity<Map<String, String>> handleEnrollmentInProgress(EnrollmentInProgressException ex) {
        Map<String, String> body = new LinkedHashMap<>();
        body.put("error", ex.getMessage());
        return ResponseEntity.status(HttpStatus.CONFLICT).body(body);
    }
}
