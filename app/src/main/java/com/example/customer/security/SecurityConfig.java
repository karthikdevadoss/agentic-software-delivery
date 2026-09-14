package com.example.customer.security;

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
import org.springframework.security.web.access.AccessDeniedHandler;
import org.springframework.security.web.AuthenticationEntryPoint;

import javax.crypto.spec.SecretKeySpec;
import java.io.IOException;
import java.util.Collection;

/**
 * Real Spring Security resource-server architecture for the Customer App.
 *
 * Public: static entry point ("/", swagger/api-docs so any consumer can
 * discover the real contract, H2 console for local dev, and the demo
 * token issuance endpoint itself -- issuing a token requires no prior
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
    public SecurityFilterChain securityFilterChain(HttpSecurity http, JwtDecoder jwtDecoder) throws Exception {
        http
                .csrf(csrf -> csrf.disable())
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .headers(headers -> headers.frameOptions(HeadersConfigurer.FrameOptionsConfig::sameOrigin))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/", "/index.html", "/static/**", "/h2-console/**",
                                "/v3/api-docs/**", "/swagger-ui/**", "/swagger-ui.html").permitAll()
                        .requestMatchers(HttpMethod.POST, "/auth/demo-token").permitAll()
                        .requestMatchers(HttpMethod.GET, "/customers/*/preferences").hasAuthority("SCOPE_preference:read")
                        .requestMatchers(HttpMethod.PUT, "/customers/*/preferences").hasAuthority("SCOPE_preference:write")
                        .requestMatchers(HttpMethod.GET, "/customers/*/plan").hasAuthority("SCOPE_contract:read")
                        .requestMatchers(HttpMethod.POST, "/customers/*/plan").hasAuthority("SCOPE_contract:write")
                        .requestMatchers(HttpMethod.GET, "/customers/*/appointment-availability").hasAuthority("SCOPE_appointment:read")
                        .requestMatchers(HttpMethod.POST, "/customers").hasAuthority("SCOPE_customer:write")
                        .requestMatchers(HttpMethod.GET, "/customers/*").hasAuthority("SCOPE_customer:read")
                        .anyRequest().authenticated())
                .oauth2ResourceServer(oauth2 -> oauth2
                        .jwt(jwt -> jwt.decoder(jwtDecoder))
                        .authenticationEntryPoint(jsonAuthenticationEntryPoint())
                        .accessDeniedHandler(jsonAccessDeniedHandler()));

        return http.build();
    }

    /**
     * Validates signature (via the shared HMAC secret), expiry, not-before,
     * issuer, and audience -- every dimension PHASE 4 requires, not just
     * signature checking.
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

    /** 401 with the same {"error": "..."} JSON shape as GlobalExceptionHandler, instead of Spring Security's default empty body. */
    private AuthenticationEntryPoint jsonAuthenticationEntryPoint() {
        return (request, response, authException) -> writeJsonError(response, 401, "authentication required or token invalid/expired");
    }

    /** 403 for an authenticated caller whose token lacks the scope a specific operation requires. */
    private AccessDeniedHandler jsonAccessDeniedHandler() {
        return (request, response, accessDeniedException) -> writeJsonError(response, 403, "token does not grant the required scope for this operation");
    }

    private static void writeJsonError(jakarta.servlet.http.HttpServletResponse response, int status, String message) throws IOException {
        response.setStatus(status);
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.getWriter().write("{\"error\":\"" + message.replace("\"", "'") + "\"}");
    }
}
