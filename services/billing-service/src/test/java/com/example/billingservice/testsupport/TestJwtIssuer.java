package com.example.billingservice.testsupport;

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

/**
 * TEST-ONLY token issuer. billing-service is a resource server ONLY (see
 * SecurityConfig's Javadoc) -- it has no DemoJwtIssuer-equivalent in main
 * code, on purpose, since it never signs tokens in production. Integration
 * tests still need a validly-signed token to exercise the real, secured
 * HTTP endpoints, so this signs one directly using the SAME shared secret/
 * issuer/audience properties SecurityConfig's JwtDecoder validates against
 * -- reading them from application.properties (not duplicating the literal
 * values here) so this can never silently drift out of sync with what the
 * decoder actually expects.
 */
@Component
public class TestJwtIssuer {

    private final byte[] secretKeyBytes;
    private final String issuer;
    private final String audience;

    public TestJwtIssuer(
            @Value("${app.security.jwt.secret}") String secret,
            @Value("${app.security.jwt.issuer}") String issuer,
            @Value("${app.security.jwt.audience}") String audience) {
        this.secretKeyBytes = secret.getBytes(StandardCharsets.UTF_8);
        this.issuer = issuer;
        this.audience = audience;
    }

    public String issueToken(String... scopes) {
        Instant now = Instant.now();
        JWTClaimsSet claims = new JWTClaimsSet.Builder()
                .subject("billing-service-test-caller")
                .issuer(issuer)
                .audience(audience)
                .issueTime(Date.from(now))
                .expirationTime(Date.from(now.plus(Duration.ofMinutes(15))))
                .claim("scope", String.join(" ", scopes))
                .build();
        try {
            SignedJWT signedJwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), claims);
            signedJwt.sign(new MACSigner(secretKeyBytes));
            return signedJwt.serialize();
        } catch (com.nimbusds.jose.JOSEException e) {
            throw new IllegalStateException("Failed to sign test JWT", e);
        }
    }
}
