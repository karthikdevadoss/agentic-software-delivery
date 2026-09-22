package com.example.customerservice.security;

import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.RSAKey;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * BL-046: standard JWKS discovery endpoint for this issuer's PUBLIC key(s)
 * (RFC 7517), keyed by kid -- the way FusionAuth/Cognito expose theirs.
 * Resource servers in this repo read the public key from configuration
 * today; this endpoint is what a real deployment points them at instead
 * (NimbusJwtDecoder.withJwkSetUri) to rotate keys without redeploying.
 */
@RestController
public class JwksController {

    private final JWKSet jwkSet;

    public JwksController(@Value("${app.security.jwt.public-key}") String publicKeyBase64,
                          @Value("${app.security.jwt.key-id}") String keyId) {
        RSAKey jwk = new RSAKey.Builder(RsaKeys.publicKey(publicKeyBase64)).keyID(keyId).build();
        this.jwkSet = new JWKSet(jwk);
    }

    @GetMapping("/.well-known/jwks.json")
    public Map<String, Object> jwks() {
        return jwkSet.toJSONObject(true);
    }
}
