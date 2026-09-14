package com.example.customer.security;

import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * PORTFOLIO DEMO TOKEN ISSUER endpoint -- see {@link DemoJwtIssuer}'s
 * Javadoc for the real-vs-demo distinction. This is the one deliberately
 * public, unauthenticated endpoint that hands out a short-lived signed
 * JWT so an anonymous recruiter/interviewer can call the real secured
 * business APIs without a signup/login flow. It never accepts input and
 * never grants anything beyond {@link DemoJwtIssuer#DEMO_SCOPES}.
 */
@RestController
@Tag(name = "Demo Authentication", description = "Portfolio-only anonymous demo token issuance -- NOT a real identity provider")
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
