package com.example.billingservice.exception;

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
 * Single, centralized place for turning exceptions into HTTP responses --
 * ported from app/'s GlobalExceptionHandler, trimmed to only the
 * exceptions billing-service can actually throw (no workspace/credential/
 * rate-limit handling here -- this service has no login or per-workspace
 * access guard, see ContractPlanController's Javadoc), plus one new
 * mapping this service specifically needs.
 *
 * STATUS-CODE DESIGN DECISION (this service's own, not ported): a
 * customer-service-unreachable failure is mapped to 503 Service
 * Unavailable, not 502 Bad Gateway. billing-service is not acting as a
 * reverse proxy relaying a malformed/invalid upstream response (the
 * classic 502 case) -- it is a service whose OWN request could not
 * complete because a dependency it calls is temporarily unreachable,
 * which is exactly what 503 (RFC 9110 §15.6.4: "the server is currently
 * unable to handle the request due to a temporary overload or scheduled
 * maintenance") describes. 503 is also what a client's own retry/circuit-
 * breaker logic conventionally treats as a transient, retry-worthy
 * signal -- the correct hint to give a caller here.
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    /** 404 -- covers both "no active contract plan" (ContractPlanService.getActivePlan)
     * and "customer not found" (CustomerLookupOutcome.NOT_FOUND, see ContractPlanService.enroll()). */
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

    /** 503 for a genuinely unreachable customer-service -- see this class's
     * Javadoc for why 503, not 502. */
    @ExceptionHandler(CustomerServiceUnavailableException.class)
    public ResponseEntity<Map<String, String>> handleCustomerServiceUnavailable(CustomerServiceUnavailableException ex) {
        Map<String, String> body = new LinkedHashMap<>();
        body.put("error", ex.getMessage());
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(body);
    }
}
