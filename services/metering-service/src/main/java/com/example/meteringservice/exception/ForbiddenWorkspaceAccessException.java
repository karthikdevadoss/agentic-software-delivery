package com.example.meteringservice.exception;

/**
 * Thrown by WorkspaceAccessGuard when an authenticated USER-persona token
 * requests a customer's meter data outside its own bound workspace.
 * Ported from the exact same real gap the monolith closes (see
 * app/src/main/java/com/example/customer/exception/ForbiddenWorkspaceAccessException.java)
 * -- distinct from Spring Security's own 401/insufficient-scope handling:
 * this is an application-level authorization decision made AFTER
 * authentication already succeeded.
 */
public class ForbiddenWorkspaceAccessException extends RuntimeException {
    public ForbiddenWorkspaceAccessException(String message) {
        super(message);
    }
}
