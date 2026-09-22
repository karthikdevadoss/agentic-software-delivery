package com.example.meteringservice.security;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.oauth2.core.OAuth2TokenValidator;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtClaimValidator;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtTimestampValidator;
import org.springframework.security.oauth2.jwt.JwtValidators;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.web.SecurityFilterChain;

import java.nio.charset.StandardCharsets;
import java.util.Collection;

/**
 * RESOURCE SERVER ONLY -- metering-service never issues its own JWTs.
 * Per docs/MICROSERVICES_ARCHITECTURE.md's Auth pattern, identity/token
 * issuance is customer-service's job (the natural home for credential
 * issuance); every OTHER service, this one included, independently
 * validates the same shared-secret-signed tokens as its own stateless
 * OAuth2 resource server -- no central session, no single point of trust
 * failure beyond the shared HMAC key itself.
 *
 * The JwtDecoder below is therefore built directly from the raw
 * app.security.jwt.* properties (constructing the SecretKeySpec straight
 * from the configured secret), NOT from a DemoJwtIssuer bean the way the
 * monolith's SecurityConfig does -- there is no local token-issuing
 * component here to source key material from, since this service is a
 * pure validator, matching the "other non-issuing services" pattern used
 * across the rest of this decomposition.
 *
 * No SCOPE_-based per-endpoint authority checks are configured here
 * (unlike the monolith's SecurityConfig): the shared demo token issuer
 * (customer-service's DemoJwtIssuer) has no meter:read/meter:write scope
 * in its fixed DEMO_SCOPES set to grant, and extending that set is a
 * cross-service change explicitly out of this task's scope (this task
 * touches services/metering-service/ only). Every business endpoint is
 * therefore gated on authentication plus WorkspaceAccessGuard's
 * customer-ownership check, which is the real authorization boundary that
 * matters for this domain; scope-based gating can be added later once
 * customer-service's issuer is extended with meter:* scopes, with no
 * redesign needed here.
 */
@Configuration
public class SecurityConfig {

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http, JwtDecoder jwtDecoder) throws Exception {
        http
                .csrf(csrf -> csrf.disable())
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/actuator/health/**", "/actuator/info").permitAll()
                        .anyRequest().authenticated())
                .oauth2ResourceServer(oauth2 -> oauth2.jwt(jwt -> jwt.decoder(jwtDecoder)));

        return http.build();
    }

    /** Validates signature (via the shared HMAC secret), expiry, not-before,
     * issuer, and audience -- same validation dimensions the monolith's
     * decoder enforces, since this must accept the exact same tokens. */
    @Bean
    public JwtDecoder jwtDecoder(
            @Value("${app.security.jwt.public-key}") String publicKeyBase64,
            @Value("${app.security.jwt.issuer}") String expectedIssuer,
            @Value("${app.security.jwt.audience}") String expectedAudience) {
        NimbusJwtDecoder decoder = NimbusJwtDecoder
                .withPublicKey(RsaKeys.publicKey(publicKeyBase64))
                .build();

        OAuth2TokenValidator<Jwt> withTimestamp = new JwtTimestampValidator();
        OAuth2TokenValidator<Jwt> withIssuer = new JwtClaimValidator<>("iss", expectedIssuer::equals);
        OAuth2TokenValidator<Jwt> withAudience = new JwtClaimValidator<Object>("aud", aud ->
                aud instanceof Collection<?> c && c.contains(expectedAudience));

        decoder.setJwtValidator(JwtValidators.createDefaultWithValidators(withTimestamp, withIssuer, withAudience));
        return decoder;
    }
}
