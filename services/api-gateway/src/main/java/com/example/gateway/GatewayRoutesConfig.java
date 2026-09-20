package com.example.gateway;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.function.RouterFunction;
import org.springframework.web.servlet.function.ServerResponse;

import static org.springframework.cloud.gateway.server.mvc.filter.BeforeFilterFunctions.uri;
import static org.springframework.cloud.gateway.server.mvc.filter.LoadBalancerFilterFunctions.lb;
import static org.springframework.cloud.gateway.server.mvc.handler.GatewayRouterFunctions.route;
import static org.springframework.cloud.gateway.server.mvc.handler.HandlerFunctions.http;

/**
 * The gateway's ONLY job: route by path to the right downstream service,
 * resolved through Eureka. No business logic, no auth re-validation --
 * see docs/MICROSERVICES_ARCHITECTURE.md for why the Authorization
 * header is passed straight through untouched instead of being handled
 * here.
 *
 * REAL BUG FOUND AND FIXED during the first genuine end-to-end smoke
 * test (not catchable by any unit test, since none of those run a real
 * Eureka registry + multiple real service instances together): a plain
 * .before(uri("http://customer-service")) does NOT load-balance through
 * Eureka by itself -- it makes a literal HTTP call to a host literally
 * named "customer-service", which fails with UnknownHostException
 * (there is no DNS entry for it; "customer-service" is only a real,
 * resolvable name via Eureka's registry). The actual load-balancing
 * mechanism is LoadBalancerFilterFunctions.lb(serviceId), added as its
 * own explicit .filter(...) -- it uses Spring Cloud's LoadBalancerClient
 * to resolve the service id to a real registered instance and REPLACES
 * the URI the earlier .before(uri(...)) filter set, rather than that
 * URI's host being load-balanced automatically just because Eureka is
 * on the classpath.
 *
 * Each target service gets its OWN route builder with its OWN
 * .before(uri(...)).filter(lb(...)), then they're combined with and() in
 * a DELIBERATE order (billing/metering FIRST, the broad customer-service
 * /customers/** catch-all LAST) -- RouterFunction.and() composition is
 * standard Spring WebMVC functional routing, evaluated in combination
 * order, first-match-wins. Without this ordering, the broad
 * /customers/** catch-all would wrongly claim /customers/{id}/plan and
 * /customers/{id}/meter-readings before billing/metering ever saw them.
 */
@Configuration
public class GatewayRoutesConfig {

    @Bean
    public RouterFunction<ServerResponse> gatewayRoutes() {
        RouterFunction<ServerResponse> billing = route("billing-service")
                .GET("/customers/*/plan", http())
                .POST("/customers/*/plan", http())
                .before(uri("http://billing-service"))
                .filter(lb("billing-service"))
                .build();

        RouterFunction<ServerResponse> metering = route("metering-service")
                .GET("/customers/*/meter-readings", http())
                .POST("/customers/*/meter-readings", http())
                .GET("/customers/*/usage-summary", http())
                .before(uri("http://metering-service"))
                .filter(lb("metering-service"))
                .build();

        RouterFunction<ServerResponse> auth = route("customer-service-auth")
                .GET("/auth/**", http())
                .POST("/auth/**", http())
                .before(uri("http://customer-service"))
                .filter(lb("customer-service"))
                .build();

        RouterFunction<ServerResponse> customer = route("customer-service")
                .GET("/customers/**", http())
                .POST("/customers/**", http())
                .PUT("/customers/**", http())
                .before(uri("http://customer-service"))
                .filter(lb("customer-service"))
                .build();

        return billing.and(metering).and(auth).and(customer);
    }
}
