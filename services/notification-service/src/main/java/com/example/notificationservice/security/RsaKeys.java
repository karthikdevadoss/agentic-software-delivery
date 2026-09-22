package com.example.notificationservice.security;

import java.security.KeyFactory;
import java.security.interfaces.RSAPrivateKey;
import java.security.interfaces.RSAPublicKey;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;
import java.util.Base64;

/**
 * BL-046: RS256 key material from configuration. Resource servers hold only
 * the PUBLIC key (base64 X.509 SubjectPublicKeyInfo); the issuer alone holds
 * the private key (base64 PKCS#8). This is the same shape the Owner's real
 * NRG aggregator used to validate FusionAuth tokens -- the identity
 * provider's public key (modulus/exponent) in configuration, no shared
 * secret anywhere -- and it closes ACT-018 finding (4): one leaked service
 * can no longer mint tokens for the others.
 */
public final class RsaKeys {

    private RsaKeys() {
    }

    public static RSAPublicKey publicKey(String base64Spki) {
        try {
            byte[] der = Base64.getDecoder().decode(base64Spki.trim());
            return (RSAPublicKey) KeyFactory.getInstance("RSA").generatePublic(new X509EncodedKeySpec(der));
        } catch (Exception e) {
            throw new IllegalStateException("app.security.jwt.public-key is not a valid base64 X.509 RSA public key", e);
        }
    }

    public static RSAPrivateKey privateKey(String base64Pkcs8) {
        try {
            byte[] der = Base64.getDecoder().decode(base64Pkcs8.trim());
            return (RSAPrivateKey) KeyFactory.getInstance("RSA").generatePrivate(new PKCS8EncodedKeySpec(der));
        } catch (Exception e) {
            throw new IllegalStateException("app.security.jwt.private-key is not a valid base64 PKCS#8 RSA private key", e);
        }
    }
}
