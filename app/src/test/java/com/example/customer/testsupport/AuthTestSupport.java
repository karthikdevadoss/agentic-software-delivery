package com.example.customer.testsupport;

import com.example.customer.security.DemoJwtIssuer;
import org.springframework.http.HttpHeaders;
import org.springframework.web.client.RestTemplate;

/**
 * Shared helper so every existing RestTemplate-based integration test can
 * attach a real, validly-signed demo JWT to every request with a one-line
 * change, now that the business endpoints they exercise require
 * authentication. Not test-only shortcut security: it calls the exact
 * same {@link DemoJwtIssuer} bean production code uses.
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
