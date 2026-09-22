package com.example.gateway.bff;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.function.Supplier;

/**
 * BL-039: the aggregator / BFF pattern from the Owner's real NRG work. The
 * customer dashboard needs the customer record (customer-service), the
 * current plan (billing-service) and the usage summary (metering-service).
 * Called sequentially that is three round trips in a row; called in
 * parallel the screen takes as long as the slowest call -- and with a
 * per-call timeout, a slow dependency degrades ONE section instead of
 * the whole screen. This is the readProduct fan-out change he made in
 * July 2024 (several seconds -> about one), reproduced honestly.
 *
 * Every section is either OK with real downstream data or UNAVAILABLE with
 * the reason; nothing is cached or invented here. The caller's bearer
 * token is propagated unchanged on every outbound call (each service still
 * validates it itself -- see docs/MICROSERVICES_ARCHITECTURE.md, auth
 * pattern), and the fan-out runs on its own bounded executor.
 */
@Service
public class DashboardAggregationService {

    private static final Logger log = LoggerFactory.getLogger(DashboardAggregationService.class);

    private final RestClient restClient;
    private final ExecutorService executor;
    private final long perCallTimeoutMs;

    public DashboardAggregationService(@Qualifier("bffLoadBalancedRestClientBuilder") RestClient.Builder builder,
                                       @Qualifier("bffFanOutExecutor") ExecutorService executor,
                                       @Value("${bff.per-call-timeout-ms:1500}") long perCallTimeoutMs) {
        this.restClient = builder.build();
        this.executor = executor;
        this.perCallTimeoutMs = perCallTimeoutMs;
    }

    public Map<String, Object> dashboard(long customerId, String authorizationHeader) {
        long started = System.nanoTime();
        CompletableFuture<SectionOutcome> customer = section("customer",
                () -> get("http://customer-service/customers/" + customerId, authorizationHeader));
        CompletableFuture<SectionOutcome> plan = section("plan",
                () -> get("http://billing-service/customers/" + customerId + "/plan", authorizationHeader));
        CompletableFuture<SectionOutcome> usage = section("usage",
                () -> get("http://metering-service/customers/" + customerId + "/usage-summary", authorizationHeader));

        CompletableFuture.allOf(customer, plan, usage).join();

        Map<String, SectionOutcome> sections = new LinkedHashMap<>();
        sections.put("customer", customer.join());
        sections.put("plan", plan.join());
        sections.put("usage", usage.join());
        boolean partial = sections.values().stream().anyMatch(s -> s.status() == SectionOutcome.Status.UNAVAILABLE);

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("customerId", customerId);
        body.put("partial", partial);
        body.put("elapsedMs", TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started));
        body.put("sections", sections);
        return body;
    }

    private CompletableFuture<SectionOutcome> section(String name, Supplier<Object> call) {
        long started = System.nanoTime();
        return CompletableFuture.supplyAsync(call, executor)
                .orTimeout(perCallTimeoutMs, TimeUnit.MILLISECONDS)
                .handle((data, failure) -> {
                    long elapsed = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started);
                    if (failure == null) {
                        return SectionOutcome.ok(data, elapsed);
                    }
                    Throwable cause = failure instanceof CompletionException && failure.getCause() != null ? failure.getCause() : failure;
                    String reason = cause instanceof TimeoutException
                            ? "timed out after " + perCallTimeoutMs + " ms"
                            : cause instanceof HttpClientErrorException.NotFound
                                ? "not found"
                                : cause.getClass().getSimpleName() + ": " + cause.getMessage();
                    log.warn("dashboard section '{}' unavailable: {}", name, reason);
                    return SectionOutcome.unavailable(reason, elapsed);
                });
    }

    private Object get(String url, String authorizationHeader) {
        RestClient.RequestHeadersSpec<?> spec = restClient.get().uri(url);
        if (authorizationHeader != null && !authorizationHeader.isBlank()) {
            spec = spec.header(HttpHeaders.AUTHORIZATION, authorizationHeader);
        }
        return spec.retrieve().body(Object.class);
    }
}
