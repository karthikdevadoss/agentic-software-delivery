package com.example.customerservice.testsupport;

import com.example.customerservice.security.DemoJwtIssuer;
import org.springframework.http.HttpHeaders;
import org.springframework.web.client.RestTemplate;

/**
 * Shared helper so every RestTemplate-based integration test can attach a
 * real, validly-signed demo JWT to every request with a one-line change.
 * Not test-only shortcut security: it calls the exact same
 * {@link DemoJwtIssuer} bean production code uses.
 */
public final class AuthTestSupport {

    private AuthTestSupport() {
    }

    public static RestTemplate authenticatedRestTemplate(DemoJwtIssuer demoJwtIssuer) {
        RestTemplate restTemplate = new RestTemplate();
        String token = demoJwtIssuer.issueDemoToken();
        restTemplate.getInterceptors().add((request, body, execution) -> {
            request.getHeaders().add(HttpHeaders.AUTHORIZATION, "Bearer " + token);
            return execution.execute(request, body);
        });
        return restTemplate;
    }
}
