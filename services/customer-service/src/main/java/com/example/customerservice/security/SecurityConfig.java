package com.example.customerservice.security;

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
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.oauth2.core.OAuth2TokenValidator;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtClaimValidator;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtTimestampValidator;
import org.springframework.security.oauth2.jwt.JwtValidators;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.access.AccessDeniedHandler;
import org.springframework.security.web.AuthenticationEntryPoint;

import javax.crypto.spec.SecretKeySpec;
import java.io.IOException;
import java.util.Collection;

/**
 * Real Spring Security resource-server architecture for customer-service,
 * adapted from the monolith's own SecurityConfig -- only the customer/
 * preference/auth endpoint rules survive here; every admin/plan/
 * appointment/triage rule belongs to other services or was monolith-only
 * scope this decomposition does not carry.
 *
 * Public: static/index entry point, health/info, and the token-issuance
 * endpoints themselves (issuing a demo token requires no prior
 * authentication by design, see DemoJwtIssuer).
 *
 * Protected: every business endpoint, gated by scope-based authorities
 * derived from the JWT's "scope" claim (Spring Security's default
 * JwtAuthenticationConverter prefixes each space-delimited scope with
 * "SCOPE_" -- no custom converter needed).
 *
 * CSRF is disabled deliberately, not carelessly: this is a stateless
 * bearer-token API (SessionCreationPolicy.STATELESS, no cookies/session
 * ever issued), and CSRF protects session/cookie-authenticated browser
 * flows specifically -- it has no attack surface to protect here.
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
                        .requestMatchers("/", "/index.html", "/static/**").permitAll()
                        .requestMatchers("/actuator/health/**", "/actuator/info").permitAll()
                        // Everything else under /actuator (metrics, prometheus, env, etc.)
                        // requires at least a valid token -- no admin scope exists in
                        // this system to further restrict it to, but raw metrics/env
                        // detail should not be fully anonymous either.
                        .requestMatchers("/actuator/**").authenticated()
                        .requestMatchers(HttpMethod.POST, "/auth/demo-token").permitAll()
                        // Real login: credentials are checked server-side
                        // (BCrypt + enabled-state, see DemoLoginController)
                        // -- permitAll here means "the endpoint accepts
                        // unauthenticated requests," not "no verification
                        // happens." The persona list is public by design
                        // (a recruiter must see it before logging in).
                        .requestMatchers(HttpMethod.POST, "/auth/login").permitAll()
                        .requestMatchers(HttpMethod.GET, "/auth/personas").permitAll()
                        .requestMatchers(HttpMethod.GET, "/customers/*/preferences").hasAuthority("SCOPE_preference:read")
                        .requestMatchers(HttpMethod.PUT, "/customers/*/preferences").hasAuthority("SCOPE_preference:write")
                        .requestMatchers(HttpMethod.POST, "/customers").hasAuthority("SCOPE_customer:write")
                        .requestMatchers(HttpMethod.PUT, "/customers/*").hasAuthority("SCOPE_customer:write")
                        .requestMatchers(HttpMethod.GET, "/customers/*").hasAuthority("SCOPE_customer:read")
                        .anyRequest().authenticated())
                .oauth2ResourceServer(oauth2 -> oauth2
                        .jwt(jwt -> jwt.decoder(jwtDecoder))
                        .authenticationEntryPoint(jsonAuthenticationEntryPoint(meterRegistry))
                        .accessDeniedHandler(jsonAccessDeniedHandler(meterRegistry)));

        return http.build();
    }

    /** Real BCrypt hashing for demo_identity.password_hash -- see
     * DemoIdentitySeeder (hashes at seed time) and DemoLoginController
     * (verifies at login time). Never a plaintext comparison. */
    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    /**
     * Validates signature (via the shared HMAC secret), expiry, not-before,
     * issuer, and audience -- identical validation dimensions to the
     * monolith's own jwtDecoder, kept that way deliberately since every
     * service in this decomposition must agree on what makes a token valid.
     */
    @Bean
    public JwtDecoder jwtDecoder(
            DemoJwtIssuer demoJwtIssuer,
            @Value("${app.security.jwt.issuer}") String expectedIssuer,
            @Value("${app.security.jwt.audience}") String expectedAudience) {
        NimbusJwtDecoder decoder = NimbusJwtDecoder
                .withSecretKey(new SecretKeySpec(demoJwtIssuer.secretKeyBytes(), "HmacSHA256"))
                .build();

        OAuth2TokenValidator<Jwt> withTimestamp = new JwtTimestampValidator();
        OAuth2TokenValidator<Jwt> withIssuer = new JwtClaimValidator<>("iss", expectedIssuer::equals);
        OAuth2TokenValidator<Jwt> withAudience = new JwtClaimValidator<Object>("aud", aud ->
                aud instanceof Collection<?> c && c.contains(expectedAudience));

        decoder.setJwtValidator(JwtValidators.createDefaultWithValidators(withTimestamp, withIssuer, withAudience));
        return decoder;
    }

    /** 401 with the same {"error": "..."} JSON shape as GlobalExceptionHandler, instead of Spring Security's default empty body. Also increments a real security-rejection counter (the observability requirement). */
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
