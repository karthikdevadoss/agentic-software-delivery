package com.example.notificationservice.testsupport;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import org.springframework.http.HttpHeaders;
import org.springframework.web.client.RestTemplate;

import java.security.KeyFactory;
import java.security.interfaces.RSAPrivateKey;
import java.security.spec.PKCS8EncodedKeySpec;
import java.util.Base64;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;

/**
 * Test-only JWT minting for this RESOURCE-SERVER-ONLY service -- unlike
 * app/'s AuthTestSupport (which reuses the real DemoJwtIssuer production
 * bean, because customer-app issues its own tokens), this service has no
 * issuer bean of its own to reuse (see SecurityConfig's Javadoc: it only
 * ever validates tokens signed elsewhere). Signs directly with
 * nimbus-jose-jwt (already on the classpath transitively via
 * spring-boot-starter-oauth2-resource-server) against the SAME
 * secret/issuer/audience this service's own SecurityConfig#jwtDecoder
 * validates against, so a token minted here is genuinely
 * indistinguishable -- to this service -- from one customer-service
 * would have issued.
 */
public final class TestJwtSupport {

    private TestJwtSupport() {
    }

    public static String issueToken(String issuer, String audience) {
        try {
            Instant now = Instant.now();
            JWTClaimsSet claims = new JWTClaimsSet.Builder()
                    .subject("test-caller")
                    .issuer(issuer)
                    .audience(audience)
                    .issueTime(Date.from(now))
                    .expirationTime(Date.from(now.plus(Duration.ofMinutes(15))))
                    .claim("scope", "customer:write")
                    .build();
            SignedJWT signedJwt = new SignedJWT(new JWSHeader.Builder(JWSAlgorithm.RS256).keyID(DevJwtKeys.KEY_ID).build(), claims);
            signedJwt.sign(new RSASSASigner(devPrivateKey()));
            return signedJwt.serialize();
        } catch (com.nimbusds.jose.JOSEException e) {
            throw new IllegalStateException("Failed to sign test JWT", e);
        }
    }

    public static RestTemplate authenticatedRestTemplate(String issuer, String audience) {
        RestTemplate restTemplate = new RestTemplate();
        String token = issueToken(issuer, audience);
        restTemplate.getInterceptors().add((request, body, execution) -> {
            request.getHeaders().add(HttpHeaders.AUTHORIZATION, "Bearer " + token);
            return execution.execute(request, body);
        });
        return restTemplate;
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
