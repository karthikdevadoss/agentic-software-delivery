package com.example.authserver.identity;

import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.User;

import java.util.List;

/**
 * A real {@link org.springframework.security.core.userdetails.UserDetails}
 * carrying the extra fields (role/workspaceId/customerId) the token
 * customizer needs to put the SAME claim shape into issued access tokens
 * that the Customer App's resource server already expects (role, cid,
 * workspace_id -- see app's DemoJwtIssuer.issuePersonaToken) -- so
 * switching the Customer App from validating its own HMAC-signed tokens to
 * validating this Authorization Server's real RS256 tokens needs no change
 * to any {@code .hasAuthority(...)} rule in its SecurityConfig, only the
 * JwtDecoder wiring itself.
 */
public class DemoUserDetails extends User {

    private final String role;
    private final String workspaceId;
    private final Long customerId;

    public DemoUserDetails(DemoIdentity identity) {
        super(identity.getUsername(), identity.getPasswordHash(), identity.isEnabled(),
                true, true, true, authorities(identity));
        this.role = identity.getRole();
        this.workspaceId = identity.getWorkspaceId();
        this.customerId = identity.getCustomerId();
    }

    private static List<GrantedAuthority> authorities(DemoIdentity identity) {
        return List.of(new SimpleGrantedAuthority("ROLE_" + identity.getRole()));
    }

    public String getRole() { return role; }
    public String getWorkspaceId() { return workspaceId; }
    public Long getCustomerId() { return customerId; }
}
