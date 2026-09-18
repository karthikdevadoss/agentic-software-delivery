package com.example.authserver.config;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.RSAKey;
import com.nimbusds.jose.jwk.source.ImmutableJWKSet;
import com.nimbusds.jose.jwk.source.JWKSource;
import com.nimbusds.jose.proc.SecurityContext;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.http.MediaType;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.oauth2.server.authorization.client.InMemoryRegisteredClientRepository;
import org.springframework.security.oauth2.server.authorization.client.RegisteredClient;
import org.springframework.security.oauth2.server.authorization.client.RegisteredClientRepository;
import org.springframework.security.config.annotation.web.configurers.oauth2.server.authorization.OAuth2AuthorizationServerConfigurer;
import org.springframework.security.oauth2.server.authorization.settings.AuthorizationServerSettings;
import org.springframework.security.oauth2.server.authorization.settings.ClientSettings;
import org.springframework.security.oauth2.server.authorization.settings.TokenSettings;
import org.springframework.security.oauth2.core.AuthorizationGrantType;
import org.springframework.security.oauth2.core.ClientAuthenticationMethod;
import org.springframework.security.oauth2.core.oidc.OidcScopes;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.LoginUrlAuthenticationEntryPoint;
import org.springframework.security.web.util.matcher.MediaTypeRequestMatcher;

import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.interfaces.RSAPrivateKey;
import java.security.interfaces.RSAPublicKey;
import java.time.Duration;
import java.util.UUID;

/**
 * The real Authorization Server wiring: the OAuth2/OIDC protocol endpoints
 * (/oauth2/authorize, /oauth2/token, /oauth2/jwks, /.well-known/openid-
 * configuration, /oauth2/revoke, /oauth2/introspect -- all provided by
 * {@link OAuth2AuthorizationServerConfigurer}, none hand-built), the
 * registered client(s), and real, asymmetric (RS256) token signing.
 *
 * WHY ASYMMETRIC, NOT THE CUSTOMER APP'S OLD SHARED-HMAC-SECRET SCHEME:
 * a real Authorization Server signs with a PRIVATE key it alone holds;
 * any real resource server validates with the corresponding PUBLIC key
 * (fetched from /oauth2/jwks) -- the resource server never possesses
 * signing capability, unlike the Customer App's previous DemoJwtIssuer,
 * which shared one symmetric secret between the issuer AND validator
 * (a real, disclosed portfolio-demo simplification, not a real enterprise
 * pattern -- see that class's own Javadoc). This service is what makes
 * that disclosed gap a genuine, working Authorization Server instead.
 */
@Configuration
public class AuthorizationServerConfig {

    @Bean
    @Order(1)
    public SecurityFilterChain authorizationServerSecurityFilterChain(HttpSecurity http) throws Exception {
        // Spring Security 7.1's real API (verified directly against the
        // installed jar's own decompiled class, not assumed from an older
        // docs snippet that showed a now-outdated static-factory-method
        // pattern): a public constructor, applied via HttpSecurity#with,
        // not a static OAuth2AuthorizationServerConfigurer.authorizationServer().
        OAuth2AuthorizationServerConfigurer authorizationServerConfigurer =
                new OAuth2AuthorizationServerConfigurer();

        http
                .securityMatcher(authorizationServerConfigurer.getEndpointsMatcher())
                .with(authorizationServerConfigurer, (authorizationServer) ->
                        authorizationServer
                                .oidc(Customizer.withDefaults()))
                .authorizeHttpRequests((authorize) -> authorize.anyRequest().authenticated())
                .exceptionHandling((exceptions) -> exceptions
                        .defaultAuthenticationEntryPointFor(
                                new LoginUrlAuthenticationEntryPoint("/login"),
                                new MediaTypeRequestMatcher(MediaType.TEXT_HTML)));

        return http.build();
    }

    /**
     * Two real, distinct registered clients, matching two genuinely
     * different real-world OAuth2 use cases:
     *
     * "customer-app-web": a PUBLIC client (no client secret -- a browser
     * cannot keep one confidential), Authorization Code + PKCE (S256), the
     * current, correct standard for any browser-based client per OAuth 2.1
     * guidance. requireAuthorizationConsent is left on deliberately (real
     * consent screen, not skipped) so a real interviewer can see the real
     * scope-consent step, not just a silent redirect.
     *
     * "demo-api-client": a CONFIDENTIAL client (real secret, never
     * committed -- see application.properties), Client Credentials grant,
     * scoped to read-only business scopes only -- a real, distinct,
     * machine-to-machine demo path for quick API testing without a
     * browser redirect, deliberately never granted write/admin scopes.
     */
    @Bean
    public RegisteredClientRepository registeredClientRepository(
            @Value("${app.oauth2.customer-app-redirect-uri}") String customerAppRedirectUri,
            @Value("${app.oauth2.demo-api-client-secret}") String demoApiClientSecret) {

        RegisteredClient customerAppWeb = RegisteredClient.withId(UUID.randomUUID().toString())
                .clientId("customer-app-web")
                .clientAuthenticationMethod(ClientAuthenticationMethod.NONE)
                .authorizationGrantType(AuthorizationGrantType.AUTHORIZATION_CODE)
                .authorizationGrantType(AuthorizationGrantType.REFRESH_TOKEN)
                .redirectUri(customerAppRedirectUri)
                .scope(OidcScopes.OPENID)
                .scope(OidcScopes.PROFILE)
                .clientSettings(ClientSettings.builder()
                        .requireAuthorizationConsent(true)
                        .requireProofKey(true) // PKCE required -- non-negotiable for a public client
                        .build())
                .tokenSettings(TokenSettings.builder()
                        .accessTokenTimeToLive(Duration.ofMinutes(15))
                        .refreshTokenTimeToLive(Duration.ofHours(8))
                        .reuseRefreshTokens(false)
                        .build())
                .build();

        RegisteredClient demoApiClient = RegisteredClient.withId(UUID.randomUUID().toString())
                .clientId("demo-api-client")
                .clientSecret(demoApiClientSecret)
                .clientAuthenticationMethod(ClientAuthenticationMethod.CLIENT_SECRET_BASIC)
                .authorizationGrantType(AuthorizationGrantType.CLIENT_CREDENTIALS)
                .scope("customer:read")
                .scope("preference:read")
                .scope("contract:read")
                .scope("appointment:read")
                .tokenSettings(TokenSettings.builder()
                        .accessTokenTimeToLive(Duration.ofMinutes(15))
                        .build())
                .build();

        return new InMemoryRegisteredClientRepository(customerAppWeb, demoApiClient);
    }

    @Bean
    public JWKSource<SecurityContext> jwkSource() {
        KeyPair keyPair = generateRsaKey();
        RSAPublicKey publicKey = (RSAPublicKey) keyPair.getPublic();
        RSAPrivateKey privateKey = (RSAPrivateKey) keyPair.getPrivate();
        RSAKey rsaKey = new RSAKey.Builder(publicKey)
                .privateKey(privateKey)
                .keyID(UUID.randomUUID().toString())
                .algorithm(JWSAlgorithm.RS256)
                .build();
        JWKSet jwkSet = new JWKSet(rsaKey);
        return new ImmutableJWKSet<>(jwkSet);
    }

    /**
     * Generated fresh at process startup, not persisted. HONEST, DISCLOSED
     * TRADE-OFF: every restart/redeploy rotates the signing key, silently
     * invalidating any still-outstanding access/refresh token (a real
     * client must simply re-authenticate -- Spring's OAuth2 client
     * machinery already handles an invalid/expired token this way). This
     * is the correct choice for a portfolio-demo deployment issuing only
     * short-lived tokens (15 min access / 8 hr refresh) where a redeploy
     * invalidating outstanding sessions is a real, acceptable, disclosed
     * limitation -- a genuine production Authorization Server would
     * persist its key material (e.g. in a KMS or a database-backed
     * JWKSource) specifically to survive restarts without forcing
     * re-authentication; documented here rather than silently assumed.
     */
    private static KeyPair generateRsaKey() {
        try {
            KeyPairGenerator keyPairGenerator = KeyPairGenerator.getInstance("RSA");
            keyPairGenerator.initialize(2048);
            return keyPairGenerator.generateKeyPair();
        } catch (Exception ex) {
            throw new IllegalStateException("Failed to generate the Authorization Server's RSA signing key", ex);
        }
    }

    @Bean
    public AuthorizationServerSettings authorizationServerSettings(
            @Value("${app.oauth2.issuer}") String issuer) {
        return AuthorizationServerSettings.builder()
                .issuer(issuer)
                .build();
    }
}
