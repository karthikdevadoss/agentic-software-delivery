package com.example.gateway.bff;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.restclient.autoconfigure.RestClientBuilderConfigurer;
import org.springframework.cloud.client.loadbalancer.LoadBalanced;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * BL-039: the BFF's outbound plumbing. Same @LoadBalanced RestClient.Builder
 * shape billing-service already uses for its clients (resolves
 * http://customer-service etc. through the real DiscoveryClient), plus a
 * DEDICATED bounded executor for the fan-out so a burst of slow downstream
 * calls can never exhaust Tomcat's request threads -- the bulkhead
 * question an interviewer asks right after "you parallelised it".
 */
@Configuration
public class BffClientConfig {

    /**
     * The gateway's own proxy (Spring Cloud Gateway Server WebMVC's http()
     * handler) builds its RestClient from the RestClient.Builder bean in
     * the context. Without this @Primary PLAIN builder it would pick up the
     * @LoadBalanced one below and try to load-balance URIs the lb() filter
     * has already resolved -- every routed call then fails with 500
     * (observed for real in GatewayRoutingIntegrationTest before this bean
     * existed). billing-service's BillingCustomerClientConfig has the same
     * pair for the same reason.
     */
    @Bean
    @Primary
    public RestClient.Builder plainRestClientBuilder(RestClientBuilderConfigurer configurer) {
        return configurer.configure(RestClient.builder());
    }

    @Bean
    @LoadBalanced
    public RestClient.Builder bffLoadBalancedRestClientBuilder(RestClientBuilderConfigurer configurer,
                                                               @Value("${bff.per-call-timeout-ms:1500}") int perCallTimeoutMs) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(perCallTimeoutMs);
        factory.setReadTimeout(perCallTimeoutMs);
        return configurer.configure(RestClient.builder().requestFactory(factory));
    }

    @Bean(destroyMethod = "shutdownNow")
    public ExecutorService bffFanOutExecutor(@Value("${bff.fan-out-threads:8}") int threads) {
        AtomicInteger counter = new AtomicInteger();
        ThreadFactory factory = runnable -> {
            Thread thread = new Thread(runnable, "bff-fan-out-" + counter.incrementAndGet());
            thread.setDaemon(true);
            return thread;
        };
        return Executors.newFixedThreadPool(threads, factory);
    }
}
