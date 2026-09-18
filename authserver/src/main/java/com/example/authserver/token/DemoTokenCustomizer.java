package com.example.authserver.token;

import com.example.authserver.identity.DemoUserDetails;
import org.springframework.security.oauth2.server.authorization.OAuth2TokenType;
import org.springframework.security.oauth2.server.authorization.token.JwtEncodingContext;
import org.springframework.security.oauth2.server.authorization.token.OAuth2TokenCustomizer;
import org.springframework.stereotype.Component;

import java.util.LinkedHashSet;
import java.util.Set;

/**
 * Stamps the SAME claim shape onto every real, issued ACCESS token that the
 * Customer App's resource server already expects (see app's DemoJwtIssuer
 * for the original, pre-Authorization-Server version of this exact
 * claim set): "scope" (space-delimited business scopes), "role", "cid"
 * (customer id, USER personas only), "workspace_id".
 *
 * DELIBERATE DESIGN CHOICE: the real business scope set is computed HERE,
 * server-side, from the authenticated principal's own real role -- never
 * trusted from whatever scope the client happened to request in its
 * authorization request. A client asking for a scope it has no real
 * business claim to (there is no client-side way to request "admin:read"
 * and receive it just by asking) cannot grant itself more than its real
 * authenticated identity actually has -- the same "authorization decided
 * by real, verified server-side state, never client input" principle this
 * whole platform applies everywhere else (see WorkspaceAccessGuard in the
 * Customer App, risk_policy.classify() in the agent platform).
 */
@Component
public class DemoTokenCustomizer implements OAuth2TokenCustomizer<JwtEncodingContext> {

    /** Mirrors DemoJwtIssuer.DEMO_SCOPES in the Customer App exactly -- every
     * authenticated demo persona, USER or ADMIN, gets this full business
     * scope set; kept as a literal duplicate (not a shared library) since
     * these are two genuinely separate deployables and this set is small,
     * stable, and explicitly documented here as the single source of truth
     * for what THIS Authorization Server ever grants. */
    private static final Set<String> DEMO_SCOPES = Set.of(
            "customer:read", "customer:write",
            "preference:read", "preference:write",
            "contract:read", "contract:write",
            "appointment:read");

    private static final String ADMIN_SCOPE = "admin:read";

    @Override
    public void customize(JwtEncodingContext context) {
        if (!OAuth2TokenType.ACCESS_TOKEN.equals(context.getTokenType())) {
            return;
        }
        if (!(context.getPrincipal().getPrincipal() instanceof DemoUserDetails user)) {
            return;
        }

        Set<String> scopes = new LinkedHashSet<>(DEMO_SCOPES);
        if ("ADMIN".equals(user.getRole())) {
            scopes.add(ADMIN_SCOPE);
        }

        context.getClaims().claim("scope", String.join(" ", scopes));
        context.getClaims().claim("role", user.getRole());
        context.getClaims().claim("workspace_id", user.getWorkspaceId());
        if (user.getCustomerId() != null) {
            context.getClaims().claim("cid", user.getCustomerId());
        }
    }
}
