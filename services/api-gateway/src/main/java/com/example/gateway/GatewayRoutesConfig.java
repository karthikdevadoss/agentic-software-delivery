package com.example.gateway;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.function.RouterFunction;
import org.springframework.web.servlet.function.ServerResponse;

import static org.springframework.cloud.gateway.server.mvc.filter.BeforeFilterFunctions.uri;
import static org.springframework.cloud.gateway.server.mvc.handler.GatewayRouterFunctions.route;
import static org.springframework.cloud.gateway.server.mvc.handler.HandlerFunctions.http;

/**
 * The gateway's ONLY job: route by path to the right downstream service,
 * resolved through Eureka (the "http://customer-service" style URI is a
 * logical service-id, not a real host -- Eureka's client-side load
 * balancer resolves it to a real registered instance). No business logic,
 * no auth re-validation -- see docs/MICROSERVICES_ARCHITECTURE.md for why
 * the Authorization header is passed straight through untouched instead
 * of being handled here.
 *
 * Each target service gets its OWN route builder with its OWN
 * .before(uri(...)), then they're combined with and() in a DELIBERATE
 * order (billing/metering FIRST, the broad customer-service /customers/**
 * catch-all LAST) -- RouterFunction.and() composition is standard Spring
 * WebMVC functional routing, evaluated in combination order,
 * first-match-wins. Without this ordering, the broad /customers/**
 * catch-all would wrongly claim /customers/{id}/plan and
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
                .build();

        RouterFunction<ServerResponse> metering = route("metering-service")
                .GET("/customers/*/meter-readings", http())
                .POST("/customers/*/meter-readings", http())
                .GET("/customers/*/usage-summary", http())
                .before(uri("http://metering-service"))
                .build();

        RouterFunction<ServerResponse> auth = route("customer-service-auth")
                .GET("/auth/**", http())
                .POST("/auth/**", http())
                .before(uri("http://customer-service"))
                .build();

        RouterFunction<ServerResponse> customer = route("customer-service")
                .GET("/customers/**", http())
                .POST("/customers/**", http())
                .PUT("/customers/**", http())
                .before(uri("http://customer-service"))
                .build();

        return billing.and(metering).and(auth).and(customer);
    }
}
