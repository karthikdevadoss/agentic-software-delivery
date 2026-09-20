package com.example.customer.security;

import com.example.customer.exception.RateLimitExceededException;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Duration;

/**
 * PORTFOLIO DEMO TOKEN ISSUER endpoint -- see {@link DemoJwtIssuer}'s
 * Javadoc for the real-vs-demo distinction. This is the one deliberately
 * public, unauthenticated endpoint that hands out a short-lived signed
 * JWT so an anonymous recruiter/interviewer can call the real secured
 * business APIs without a signup/login flow. It never accepts input and
 * never grants anything beyond {@link DemoJwtIssuer#DEMO_SCOPES}.
 *
 * RATE LIMITED (see RateLimiterService's Javadoc for the algorithm/
 * fail-open reasoning): this is the single most naturally abusable
 * endpoint in the app -- unauthenticated by design, and every call mints
 * a real signed credential. 20 tokens per minute per client IP is
 * generous for genuine interview/demo use (a person clicking around) and
 * still a real, meaningful ceiling against a scripted hammering loop.
 */
@RestController
@Tag(name = "Demo Authentication", description = "Portfolio-only anonymous demo token issuance -- NOT a real identity provider")
public class DemoAuthController {

    static final int RATE_LIMIT = 20;
    static final Duration RATE_LIMIT_WINDOW = Duration.ofMinutes(1);

    public record TokenResponse(String access_token, String token_type, long expires_in, String scope) {
    }

    private final DemoJwtIssuer demoJwtIssuer;
    private final RateLimiterService rateLimiterService;

    public DemoAuthController(DemoJwtIssuer demoJwtIssuer, RateLimiterService rateLimiterService) {
        this.demoJwtIssuer = demoJwtIssuer;
        this.rateLimiterService = rateLimiterService;
    }

    @PostMapping("/auth/demo-token")
    public TokenResponse issueDemoToken(HttpServletRequest request) {
        String clientKey = clientIp(request);
        if (!rateLimiterService.allow("demo-token", clientKey, RATE_LIMIT, RATE_LIMIT_WINDOW)) {
            throw new RateLimitExceededException(
                    "Too many demo-token requests -- limit is " + RATE_LIMIT + " per " + RATE_LIMIT_WINDOW.toSeconds() + "s, please slow down");
        }

        String token = demoJwtIssuer.issueDemoToken();
        return new TokenResponse(
                token,
                "Bearer",
                demoJwtIssuer.getDefaultTtl().toSeconds(),
                String.join(" ", DemoJwtIssuer.DEMO_SCOPES));
    }

    /** X-Forwarded-For aware: Railway (and most PaaS front doors) sits
     * behind a proxy, so request.getRemoteAddr() alone would see the
     * proxy's own address for every caller, collapsing everyone into one
     * shared rate-limit bucket. Takes the first (client-nearest) entry
     * when the header is present, falls back to the direct remote
     * address for local/test runs where no proxy is involved. */
    private static String clientIp(HttpServletRequest request) {
        String forwardedFor = request.getHeader("X-Forwarded-For");
        if (forwardedFor != null && !forwardedFor.isBlank()) {
            return forwardedFor.split(",")[0].trim();
        }
        return request.getRemoteAddr();
    }
}
