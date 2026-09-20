package com.example.meteringservice.testsupport;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;

/**
 * Test-only JWT signer for metering-service integration tests.
 *
 * Unlike the monolith's AuthTestSupport (app/src/test/java/com/example/
 * customer/testsupport/AuthTestSupport.java), which reuses a real
 * production DemoJwtIssuer bean, this service has NO production token
 * issuer at all -- it is a resource server only (see SecurityConfig's
 * Javadoc), by real architectural design: token issuance lives in
 * customer-service in this decomposition. So this class exists
 * exclusively under src/test, signs with the same HMAC secret the
 * service's own JwtDecoder validates against (read from the same
 * app.security.jwt.* properties by the calling test), and mints only the
 * "role"/"cid" claims WorkspaceAccessGuard actually reads -- it is not,
 * and must never become, a second production token issuer.
 */
public final class TestJwtIssuer {

    private TestJwtIssuer() {
    }

    /**
     * @param role if non-null, sets the "role" claim (e.g. "USER"/"ADMIN");
     *             a null role produces the monolith's "unscoped/legacy"
     *             token shape (no role claim at all), which
     *             WorkspaceAccessGuard treats as bypassing the check.
     * @param customerId if non-null, sets the "cid" claim binding this
     *                   token to exactly one customer.
     */
    public static String issueToken(String secret, String issuer, String audience, String role, Long customerId) {
        Instant now = Instant.now();
        JWTClaimsSet.Builder builder = new JWTClaimsSet.Builder()
                .subject("metering-service-test-user")
                .issuer(issuer)
                .audience(audience)
                .issueTime(Date.from(now))
                .expirationTime(Date.from(now.plus(Duration.ofMinutes(5))));
        if (role != null) {
            builder.claim("role", role);
        }
        if (customerId != null) {
            builder.claim("cid", customerId);
        }
        try {
            SignedJWT signedJwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), builder.build());
            signedJwt.sign(new MACSigner(secret.getBytes(StandardCharsets.UTF_8)));
            return signedJwt.serialize();
        } catch (JOSEException e) {
            throw new IllegalStateException("Failed to sign test JWT", e);
        }
    }
}
