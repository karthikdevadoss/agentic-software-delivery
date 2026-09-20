package com.example.notificationservice.exception;

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
 * Single, centralized place for turning exceptions into HTTP responses,
 * same reasoning as app/'s GlobalExceptionHandler: structured JSON on
 * every error response instead of a raw stack trace or plain-text body.
 * Scoped down to what this service's small surface (POST /notifications/send
 * plus the Kafka consumer) actually needs -- validation failures and a
 * general-purpose bad-request/not-found mapping -- rather than porting
 * the monolith's much larger exception set (workspace access, rate
 * limiting, enrollment locking, login) that has no equivalent here.
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
     * that isn't Bean-Validation-annotation-driven (e.g. an unrecognized
     * NotificationChannel value) -- same reusable mapping app/'s
     * GlobalExceptionHandler uses. */
    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, String>> handleBadRequest(IllegalArgumentException ex) {
        Map<String, String> body = new LinkedHashMap<>();
        body.put("error", ex.getMessage());
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(body);
    }

    /** 500->400 style mapping for NotificationSenderFactory's own fail-loud
     * signal (no sender registered for a channel) -- a real, if unlikely
     * (every declared NotificationChannel currently has a registered
     * sender), misconfiguration should surface as a clean 400, not an
     * unmapped 500. */
    @ExceptionHandler(IllegalStateException.class)
    public ResponseEntity<Map<String, String>> handleIllegalState(IllegalStateException ex) {
        Map<String, String> body = new LinkedHashMap<>();
        body.put("error", ex.getMessage());
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(body);
    }
}
