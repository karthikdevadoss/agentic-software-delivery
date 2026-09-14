package com.example.customer.exception;

/**
 * Thrown by WorkspaceAccessGuard when an authenticated USER-persona token
 * requests a customer's data outside its own bound workspace. Distinct
 * from Spring Security's own insufficient_scope 403 (SecurityConfig's
 * AccessDeniedHandler) -- this is an application-level authorization
 * decision made AFTER authentication and scope checks already passed.
 */
public class ForbiddenWorkspaceAccessException extends RuntimeException {
    public ForbiddenWorkspaceAccessException(String message) {
        super(message);
    }
}
