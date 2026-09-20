package com.example.billingservice.security;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configurers.HeadersConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.oauth2.core.OAuth2TokenValidator;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtClaimValidator;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtTimestampValidator;
import org.springframework.security.oauth2.jwt.JwtValidators;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.security.web.access.AccessDeniedHandler;

import javax.crypto.spec.SecretKeySpec;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Collection;

/**
 * RESOURCE SERVER ONLY, unlike app/'s SecurityConfig: billing-service
 * never issues JWTs (no DemoJwtIssuer, no login endpoint here) -- identity
 * issuance is customer-service's job (see
 * docs/MICROSERVICES_ARCHITECTURE.md's "Why Customer Service owns auth").
 * This service only VALIDATES tokens signed with the same shared HMAC
 * secret every service in this decomposition trusts (see
 * app.security.jwt.* in application.properties). The JwtDecoder below is
 * built directly from that shared secret property, not from an issuer
 * bean -- there is no local issuer to borrow key material from.
 *
 * CSRF is disabled deliberately, not carelessly: same reasoning as app/'s
 * SecurityConfig -- this is a stateless bearer-token API
 * (SessionCreationPolicy.STATELESS, no cookies/session ever issued), and
 * CSRF protects session/cookie-authenticated browser flows specifically.
 */
@Configuration
public class SecurityConfig {

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http, JwtDecoder jwtDecoder, MeterRegistry meterRegistry) throws Exception {
        http
                .csrf(csrf -> csrf.disable())
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .headers(headers -> headers.frameOptions(HeadersConfigurer.FrameOptionsConfig::sameOrigin))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/actuator/health/**", "/actuator/info").permitAll()
                        // Everything else under /actuator (metrics, prometheus, env, etc.)
                        // requires at least a valid token -- same rule as app/'s
                        // SecurityConfig: no admin scope exists in this service to
                        // further restrict it to, but raw metrics/env detail should
                        // not be fully anonymous either.
                        .requestMatchers("/actuator/**").authenticated()
                        .requestMatchers(HttpMethod.GET, "/customers/*/plan").hasAuthority("SCOPE_contract:read")
                        .requestMatchers(HttpMethod.POST, "/customers/*/plan").hasAuthority("SCOPE_contract:write")
                        .anyRequest().authenticated())
                .oauth2ResourceServer(oauth2 -> oauth2
                        .jwt(jwt -> jwt.decoder(jwtDecoder))
                        .authenticationEntryPoint(jsonAuthenticationEntryPoint(meterRegistry))
                        .accessDeniedHandler(jsonAccessDeniedHandler(meterRegistry)));

        return http.build();
    }

    /**
     * Built directly from app.security.jwt.secret -- deliberately NOT
     * routed through a DemoJwtIssuer-equivalent bean (this service has
     * none: it never signs tokens, only validates them). Validates
     * signature (via the shared HMAC secret), expiry, not-before, issuer,
     * and audience -- every dimension app/'s own JwtDecoder validates,
     * unchanged.
     */
    @Bean
    public JwtDecoder jwtDecoder(
            @Value("${app.security.jwt.secret}") String secret,
            @Value("${app.security.jwt.issuer}") String expectedIssuer,
            @Value("${app.security.jwt.audience}") String expectedAudience) {
        NimbusJwtDecoder decoder = NimbusJwtDecoder
                .withSecretKey(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"))
                .build();

        OAuth2TokenValidator<Jwt> withTimestamp = new JwtTimestampValidator();
        OAuth2TokenValidator<Jwt> withIssuer = new JwtClaimValidator<>("iss", expectedIssuer::equals);
        OAuth2TokenValidator<Jwt> withAudience = new JwtClaimValidator<Object>("aud", aud ->
                aud instanceof Collection<?> c && c.contains(expectedAudience));

        decoder.setJwtValidator(JwtValidators.createDefaultWithValidators(withTimestamp, withIssuer, withAudience));
        return decoder;
    }

    /** 401 with the same {"error": "..."} JSON shape as GlobalExceptionHandler, instead of Spring Security's default empty body. Also increments a real security-rejection counter. */
    private AuthenticationEntryPoint jsonAuthenticationEntryPoint(MeterRegistry meterRegistry) {
        Counter counter = Counter.builder("security.rejections")
                .tag("reason", "unauthenticated")
                .description("Requests rejected because no valid, non-expired, correctly-signed/issued token was presented")
                .register(meterRegistry);
        return (request, response, authException) -> {
            counter.increment();
            writeJsonError(response, 401, "authentication required or token invalid/expired");
        };
    }

    /** 403 for an authenticated caller whose token lacks the scope a specific operation requires. Also increments a real security-rejection counter. */
    private AccessDeniedHandler jsonAccessDeniedHandler(MeterRegistry meterRegistry) {
        Counter counter = Counter.builder("security.rejections")
                .tag("reason", "insufficient_scope")
                .description("Requests rejected because the authenticated token lacked the scope the operation required")
                .register(meterRegistry);
        return (request, response, accessDeniedException) -> {
            counter.increment();
            writeJsonError(response, 403, "token does not grant the required scope for this operation");
        };
    }

    private static void writeJsonError(jakarta.servlet.http.HttpServletResponse response, int status, String message) throws IOException {
        response.setStatus(status);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.getWriter().write("{\"error\":\"" + message.replace("\"", "'") + "\"}");
    }
}
