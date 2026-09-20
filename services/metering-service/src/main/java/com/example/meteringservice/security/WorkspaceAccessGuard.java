package com.example.meteringservice.security;

import com.example.meteringservice.exception.ForbiddenWorkspaceAccessException;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Component;

/**
 * Enforces the exact same per-persona workspace isolation the monolith
 * already enforces (see
 * app/src/main/java/com/example/customer/security/WorkspaceAccessGuard.java)
 * -- replicated here rather than reinvented, checking the SAME claim
 * names ("role", "cid") a token from customer-service's DemoJwtIssuer
 * actually carries, since this service never issues tokens itself (see
 * SecurityConfig's Javadoc) and must interoperate with tokens minted
 * elsewhere in this decomposition.
 *
 * A USER-role persona token may only read/submit meter readings for the
 * ONE customer bound to its own "cid" claim -- never another customer's
 * data, even by guessing/incrementing an id in the URL. An ADMIN-role
 * token bypasses this check, same as the monolith. A token with no
 * "role" claim at all (the monolith's pre-existing anonymous demo token)
 * is treated as unscoped/legacy and also bypasses this check, exactly
 * matching the monolith's already-shipped behavior for that token shape.
 */
@Component
public class WorkspaceAccessGuard {

    public void assertAccessible(Long requestedCustomerId, Jwt jwt) {
        Object roleClaim = jwt.getClaim("role");
        if (roleClaim == null || "ADMIN".equals(roleClaim)) {
            return;
        }
        Object cidClaim = jwt.getClaim("cid");
        Long ownCustomerId = cidClaim instanceof Number n ? n.longValue() : null;
        if (ownCustomerId == null || !ownCustomerId.equals(requestedCustomerId)) {
            throw new ForbiddenWorkspaceAccessException(
                    "This identity is not authorized for customer " + requestedCustomerId);
        }
    }
}
