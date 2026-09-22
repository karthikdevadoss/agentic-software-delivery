package com.example.gateway.bff;

import org.springframework.http.HttpHeaders;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * BL-039: the one "screen" endpoint of the BFF. The gateway's router
 * functions forward /customers/** etc. one-to-one; this path is different:
 * a single call the mobile/web dashboard makes, answered by fanning out to
 * three services in parallel (see DashboardAggregationService). The
 * response always carries "partial" so the client can render what it got
 * and show "temporarily unavailable" for the rest.
 */
@RestController
public class DashboardController {

    private final DashboardAggregationService aggregationService;

    public DashboardController(DashboardAggregationService aggregationService) {
        this.aggregationService = aggregationService;
    }

    @GetMapping("/bff/customers/{customerId}/dashboard")
    public Map<String, Object> dashboard(@PathVariable long customerId,
                                         @RequestHeader(value = HttpHeaders.AUTHORIZATION, required = false) String authorization) {
        return aggregationService.dashboard(customerId, authorization);
    }
}
