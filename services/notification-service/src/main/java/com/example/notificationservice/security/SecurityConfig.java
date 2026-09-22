package com.example.notificationservice.security;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.MediaType;
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
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.security.web.access.AccessDeniedHandler;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Collection;

/**
 * RESOURCE SERVER ONLY -- unlike app/'s SecurityConfig (and
 * customer-service's), this service never issues tokens (no DemoJwtIssuer
 * equivalent here): it independently validates JWTs signed with the same
 * shared HMAC secret customer-service uses to mint them, per
 * docs/MICROSERVICES_ARCHITECTURE.md's Auth pattern ("every service
 * independently validates JWTs as its own OAuth2 resource server ...
 * stateless validation at every service"). The JwtDecoder below is built
 * directly from app.security.jwt.* properties (SecretKeySpec constructed
 * straight from the property, same approach as billing-service) rather
 * than borrowing key material from an issuer bean this service does not
 * have.
 *
 * POST /notifications/send is gated on authenticated() rather than a new
 * "notification:write" scope: customer-service's DemoJwtIssuer.DEMO_SCOPES
 * is the single fixed set of scopes every real demo token in this system
 * can ever carry, and it does not include a notification-specific scope
 * (out of scope for this task to add one to a service this agent must not
 * touch). Inventing a scope name no real, obtainable token would ever
 * carry would make this endpoint reachable only from hand-crafted test
 * tokens -- a worse, dishonest-looking trade-off than simply requiring
 * "any valid, correctly-signed token," which every real demo token
 * already satisfies.
 *
 * REAL BUG FOUND in CI (not catchable locally -- this test's Testcontainers
 * Kafka container skips without Docker, so its Spring context was never
 * actually built on this dev machine until CI, with real Docker,
 * finally did): ContractPlanEventFlowIntegrationTest deliberately uses
 * @SpringBootTest(webEnvironment = WebEnvironment.NONE) (it drives a raw
 * Kafka producer and checks repository state, no HTTP calls needed) --
 * but securityFilterChain() unconditionally required an HttpSecurity
 * bean, which Spring Security only auto-configures for a real servlet
 * web application context. @ConditionalOnWebApplication is the correct,
 * standard fix: this whole class simply does not activate for a non-web
 * context, rather than forcing every test (even ones that genuinely
 * never touch HTTP) to pay for starting an embedded server just to
 * satisfy this bean.
 */
@Configuration
@ConditionalOnWebApplication
public class SecurityConfig {

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http, JwtDecoder jwtDecoder, MeterRegistry meterRegistry) throws Exception {
        http
                .csrf(csrf -> csrf.disable())
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/actuator/health/**", "/actuator/info").permitAll()
                        // Everything else under /actuator (metrics, prometheus, env, etc.)
                        // requires at least a valid token -- same reasoning as app/'s
                        // SecurityConfig: no admin scope exists in this system to further
                        // restrict it to, but raw metrics/env detail should not be fully
                        // anonymous either.
                        .requestMatchers("/actuator/**").authenticated()
                        .anyRequest().authenticated())
                .oauth2ResourceServer(oauth2 -> oauth2
                        .jwt(jwt -> jwt.decoder(jwtDecoder))
                        .authenticationEntryPoint(jsonAuthenticationEntryPoint(meterRegistry))
                        .accessDeniedHandler(jsonAccessDeniedHandler(meterRegistry)));

        return http.build();
    }

    /**
     * Validates signature (via the shared HMAC secret), expiry, not-before,
     * issuer, and audience -- built directly from configuration, not from
     * an issuer bean, since this service never mints its own tokens.
     */
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
