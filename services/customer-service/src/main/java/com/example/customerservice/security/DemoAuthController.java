package com.example.customerservice.security;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * PORTFOLIO DEMO TOKEN ISSUER endpoint -- see {@link DemoJwtIssuer}'s
 * Javadoc for the real-vs-demo distinction. This is the one deliberately
 * public, unauthenticated endpoint that hands out a short-lived signed
 * JWT so an anonymous recruiter/interviewer can call the real secured
 * business APIs without a signup/login flow. It never accepts input and
 * never grants anything beyond {@link DemoJwtIssuer#DEMO_SCOPES}.
 *
 * WITHOUT RATE LIMITING, unlike the monolith's DemoAuthController: this
 * service's pom has no Redis dependency (see docs/MICROSERVICES_
 * ARCHITECTURE.md's Data section -- Redis stays scoped to billing-service's
 * enrollment lock in this decomposition), so RateLimiterService is not
 * ported here. The token is issued directly.
 */
@RestController
public class DemoAuthController {

    public record TokenResponse(String access_token, String token_type, long expires_in, String scope) {
    }

    private final DemoJwtIssuer demoJwtIssuer;

    public DemoAuthController(DemoJwtIssuer demoJwtIssuer) {
        this.demoJwtIssuer = demoJwtIssuer;
    }

    @PostMapping("/auth/demo-token")
    public TokenResponse issueDemoToken() {
        String token = demoJwtIssuer.issueDemoToken();
        return new TokenResponse(
                token,
                "Bearer",
                demoJwtIssuer.getDefaultTtl().toSeconds(),
                String.join(" ", DemoJwtIssuer.DEMO_SCOPES));
    }
}
