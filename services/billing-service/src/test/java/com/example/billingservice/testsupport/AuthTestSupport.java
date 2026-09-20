package com.example.billingservice.testsupport;

import org.springframework.http.HttpHeaders;
import org.springframework.web.client.RestTemplate;

/**
 * Shared helper so every RestTemplate-based integration test can attach a
 * real, validly-signed test JWT to every request with a one-line change --
 * mirrors app/'s own AuthTestSupport, adapted to use TestJwtIssuer instead
 * of a production DemoJwtIssuer (this service has none, see
 * TestJwtIssuer's Javadoc).
 */
public final class AuthTestSupport {

    private AuthTestSupport() {
    }

    public static RestTemplate authenticatedRestTemplate(TestJwtIssuer jwtIssuer) {
        RestTemplate restTemplate = new RestTemplate();
        String token = jwtIssuer.issueToken("contract:read", "contract:write");
        restTemplate.getInterceptors().add((request, body, execution) -> {
            request.getHeaders().add(HttpHeaders.AUTHORIZATION, "Bearer " + token);
            return execution.execute(request, body);
        });
        return restTemplate;
    }
}
