package com.example.meteringservice.exception;

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
 * Single, centralized place for turning this service's exceptions into
 * HTTP responses -- same pattern the monolith already uses (see
 * app/src/main/java/com/example/customer/exception/GlobalExceptionHandler.java),
 * reused here rather than reinvented. Every error response is structured
 * JSON, never a raw stack trace or plain-text body.
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    /** 404 for a not-found resource. No endpoint in this service currently
     * throws NoSuchElementException (a customer with zero readings is a
     * normal, valid empty history, not a 404 -- see
     * MeterReadingService.getHistory's Javadoc) -- kept here, matching the
     * monolith's pattern, as the correct real mapping for the day this
     * service gains a single-reading-by-id lookup or a genuine
     * cross-service existence check. */
    @ExceptionHandler(NoSuchElementException.class)
    public ResponseEntity<Map<String, String>> handleNotFound(NoSuchElementException ex) {
        Map<String, String> body = new LinkedHashMap<>();
        body.put("error", ex.getMessage());
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(body);
    }

    /** 400 for a request body that failed Bean Validation (@NotBlank,
     * @NotNull, @Positive, @NotInFuture on MeterReadingRequest). */
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

    /** 400 for a request-level validation failure that isn't Bean-
     * Validation-annotation-driven -- specifically, getUsageSummary's
     * from-after-to check, which can only be evaluated once both query
     * params are in hand together, not per-field. */
    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, String>> handleBadRequest(IllegalArgumentException ex) {
        Map<String, String> body = new LinkedHashMap<>();
        body.put("error", ex.getMessage());
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(body);
    }

    /** 403 for an authenticated, correctly-signed USER-persona token that
     * requested a customer outside its own bound workspace. */
    @ExceptionHandler(ForbiddenWorkspaceAccessException.class)
    public ResponseEntity<Map<String, String>> handleForbiddenWorkspace(ForbiddenWorkspaceAccessException ex) {
        Map<String, String> body = new LinkedHashMap<>();
        body.put("error", ex.getMessage());
        return ResponseEntity.status(HttpStatus.FORBIDDEN).body(body);
    }
}
