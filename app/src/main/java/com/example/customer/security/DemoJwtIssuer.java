package com.example.customer.security;

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
 * provider. A real enterprise deployment of this architecture would issue
 * tokens from Cognito/Keycloak/FusionAuth/an enterprise IdP, with this
 * application acting purely as an OAuth2 resource server validating
 * tokens it did not itself mint. This class exists solely so an anonymous
 * recruiter/interviewer can experience the real secured API without a
 * signup/login flow -- it signs its own tokens with a symmetric secret
 * this same application also uses to validate them (see
 * {@link SecurityConfig#jwtDecoder}).
 *
 * Tokens are cryptographically signed (HS256), short-lived, and carry
 * only a fixed, explicit set of business-scoped read/write authorities --
 * never admin/owner/deployment/infrastructure/shell capabilities, because
 * no such scope exists in {@link #DEMO_SCOPES} for a caller to be granted
 * in the first place.
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
        try {
            JWTClaimsSet claims = new JWTClaimsSet.Builder()
                    .subject("anonymous-demo-user")
                    .issuer(issuer)
                    .audience(audience)
                    .issueTime(Date.from(now))
                    .expirationTime(Date.from(now.plus(ttl)))
                    .claim("scope", String.join(" ", scopes))
                    .build();
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
