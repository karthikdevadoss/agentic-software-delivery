package com.example.meteringservice.testsupport;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;

import java.security.KeyFactory;
import java.security.interfaces.RSAPrivateKey;
import java.security.spec.PKCS8EncodedKeySpec;
import java.util.Base64;
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
 * exclusively under src/test, signs RS256 with the test-only dev private key
 * (DevJwtKeys) whose public half the service's own JwtDecoder validates
 * against (app.security.jwt.public-key), and mints only the
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
    public static String issueToken(String issuer, String audience, String role, Long customerId) {
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
            SignedJWT signedJwt = new SignedJWT(new JWSHeader.Builder(JWSAlgorithm.RS256).keyID(DevJwtKeys.KEY_ID).build(), builder.build());
            signedJwt.sign(new RSASSASigner(devPrivateKey()));
            return signedJwt.serialize();
        } catch (JOSEException e) {
            throw new IllegalStateException("Failed to sign test JWT", e);
        }
    }

    private static RSAPrivateKey devPrivateKey() {
        try {
            byte[] der = Base64.getDecoder().decode(DevJwtKeys.PRIVATE_KEY_BASE64);
            return (RSAPrivateKey) KeyFactory.getInstance("RSA").generatePrivate(new PKCS8EncodedKeySpec(der));
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }
}
