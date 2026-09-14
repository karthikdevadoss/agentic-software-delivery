package com.example.customer.security;

import com.example.customer.exception.ForbiddenWorkspaceAccessException;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Component;

/**
 * Enforces per-persona workspace isolation on every customer-scoped
 * endpoint: a USER-role login token (see DemoLoginController/
 * DemoJwtIssuer#issuePersonaToken) may only ever read/write the ONE
 * customer bound to its own "cid" claim -- never another customer's data,
 * even by guessing/incrementing an id in the URL. An ADMIN-role token
 * bypasses this check (see the "ADMIN EXPERIENCE" requirement) but is
 * still a real, separately-scoped, server-verified JWT, never a bypass of
 * authentication itself.
 *
 * A token with NO "role" claim at all -- the pre-existing anonymous
 * /auth/demo-token issued by {@link DemoJwtIssuer#issueDemoToken()},
 * still used unchanged by existing tests and internal backend automation
 * -- is deliberately treated as unscoped/legacy and bypasses this check,
 * exactly matching its current, already-shipped, already-tested behavior.
 * Only the NEW persona login path opts into workspace scoping.
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
                    "This demo identity is not authorized for customer " + requestedCustomerId);
        }
    }
}
