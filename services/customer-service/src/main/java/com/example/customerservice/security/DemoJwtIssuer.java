package com.example.customerservice.security;

import com.example.customerservice.model.DemoIdentity;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;
import java.util.LinkedHashSet;
import java.util.Set;

/**
 * PORTFOLIO DEMO TOKEN ISSUER -- explicitly NOT an enterprise identity
 * provider. This is the ONE service in the microservices decomposition
 * that issues tokens (see docs/MICROSERVICES_ARCHITECTURE.md's Auth
 * pattern section) -- every other service only validates them, using the
 * same shared HMAC secret. A real enterprise deployment of this
 * architecture would issue tokens from Cognito/Keycloak/FusionAuth/an
 * enterprise IdP; this class exists solely so an anonymous recruiter/
 * interviewer can experience the real secured APIs across every service
 * without a signup/login flow.
 *
 * Tokens are cryptographically signed (HS256), short-lived, and carry
 * only a fixed, explicit set of business-scoped read/write authorities --
 * never admin/owner/deployment/infrastructure/shell capabilities, because
 * no such scope exists in {@link #DEMO_SCOPES} for a caller to be granted
 * in the first place.
 *
 * DEMO_SCOPES deliberately still includes the contract:read/contract:write/
 * appointment:read scopes this service's OWN endpoints never check (see
 * SecurityConfig) --
 * customer-service is the shared token issuer for the whole
 * decomposition, so a token minted here must carry every scope another
 * service (billing-service's plan endpoints, etc.) will independently
 * validate against the same shared secret.
 */
@Component
public class DemoJwtIssuer {

    /**
     * The complete, fixed set of scopes an anonymous demo token can ever
     * carry. Deliberately business-data-only -- no admin/owner/deploy/
     * infrastructure/secrets/shell scope exists anywhere in this set for a
     * demo caller to be granted, by construction, not by a runtime check.
     */
    public static final Set<String> DEMO_SCOPES = Set.copyOf(new LinkedHashSet<>(Set.of(
            "customer:read", "customer:write",
            "preference:read", "preference:write",
            "contract:read", "contract:write",
            "appointment:read")));

    /**
     * The additional scope an ADMIN-role persona token carries, ON TOP OF
     * {@link #DEMO_SCOPES} -- structurally kept out of DEMO_SCOPES itself
     * so the anonymous {@link #issueDemoToken()} path can never grant it.
     * Only {@link #issuePersonaToken} ever adds it, and only for a
     * DemoIdentity whose role is genuinely "ADMIN" (verified server-side
     * against demo_identity, never trusted from client input).
     */
    public static final Set<String> ADMIN_SCOPES = Set.of("admin:read");

    private final byte[] secretKeyBytes;
    private final String issuer;
    private final String audience;
    private final Duration defaultTtl;

    public DemoJwtIssuer(
            @Value("${app.security.jwt.secret}") String secret,
            @Value("${app.security.jwt.issuer}") String issuer,
            @Value("${app.security.jwt.audience}") String audience,
            @Value("${app.security.jwt.demo-token-ttl-seconds}") long defaultTtlSeconds) {
        this.secretKeyBytes = secret.getBytes(StandardCharsets.UTF_8);
        this.issuer = issuer;
        this.audience = audience;
        this.defaultTtl = Duration.ofSeconds(defaultTtlSeconds);
    }

    /** Issues a demo token with every allowed scope and the default TTL -- what the public /auth/demo-token endpoint actually hands out. */
    public String issueDemoToken() {
        return issueToken(DEMO_SCOPES, defaultTtl);
    }

    public Duration getDefaultTtl() {
        return defaultTtl;
    }

    /**
     * Issues a token with an explicit scope set and TTL. Package-visible
     * beyond production use only for tests that need a deliberately
     * narrow-scoped or already-expired token to prove 403/401 behavior --
     * never reachable from any HTTP endpoint.
     */
    public String issueToken(Set<String> scopes, Duration ttl) {
        if (!DEMO_SCOPES.containsAll(scopes)) {
            throw new IllegalArgumentException("Demo issuer cannot grant a scope outside DEMO_SCOPES: " + scopes);
        }
        Instant now = Instant.now();
        JWTClaimsSet claims = new JWTClaimsSet.Builder()
                .subject("anonymous-demo-user")
                .issuer(issuer)
                .audience(audience)
                .issueTime(Date.from(now))
                .expirationTime(Date.from(now.plus(ttl)))
                .claim("scope", String.join(" ", scopes))
                .build();
        return sign(claims);
    }

    /**
     * Issues a real, per-persona login token (see DemoLoginController) --
     * genuinely distinct from the anonymous {@link #issueDemoToken()}: it
     * carries the identity's own username as subject, an honest "role"
     * claim (USER/ADMIN, verified server-side against demo_identity, never
     * client-supplied), and -- for a USER identity only -- a "cid" claim
     * binding the token to exactly one customer id, which
     * WorkspaceAccessGuard enforces on every customer-scoped endpoint. An
     * ADMIN identity has no "cid" (not scoped to a single customer) but
     * gets {@link #ADMIN_SCOPES} added on top of the same business
     * DEMO_SCOPES every persona shares.
     */
    public String issuePersonaToken(DemoIdentity identity) {
        Set<String> scopes = new LinkedHashSet<>(DEMO_SCOPES);
        if ("ADMIN".equals(identity.getRole())) {
            scopes.addAll(ADMIN_SCOPES);
        }
        Instant now = Instant.now();
        JWTClaimsSet.Builder builder = new JWTClaimsSet.Builder()
                .subject(identity.getUsername())
                .issuer(issuer)
                .audience(audience)
                .issueTime(Date.from(now))
                .expirationTime(Date.from(now.plus(defaultTtl)))
                .claim("scope", String.join(" ", scopes))
                .claim("role", identity.getRole())
                .claim("workspace_id", identity.getWorkspaceId());
        if (identity.getCustomerId() != null) {
            builder.claim("cid", identity.getCustomerId());
        }
        return sign(builder.build());
    }

    private String sign(JWTClaimsSet claims) {
        try {
            SignedJWT signedJwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), claims);
            signedJwt.sign(new MACSigner(secretKeyBytes));
            return signedJwt.serialize();
        } catch (com.nimbusds.jose.JOSEException e) {
            throw new IllegalStateException("Failed to sign demo JWT", e);
        }
    }

    /** Exposed only for {@link SecurityConfig} to build the matching decoder from the same key material. */
    byte[] secretKeyBytes() {
        return secretKeyBytes;
    }
}
