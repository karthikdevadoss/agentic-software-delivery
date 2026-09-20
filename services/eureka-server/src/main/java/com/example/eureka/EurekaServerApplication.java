package com.example.eureka;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.netflix.eureka.server.EnableEurekaServer;

/**
 * The service registry for the microservices decomposition of the
 * Customer App domain -- see docs/MICROSERVICES_ARCHITECTURE.md. Every
 * other service (customer/billing/notification/metering-service,
 * api-gateway) registers here as a Eureka client instead of any service
 * hardcoding another service's URL.
 */
@SpringBootApplication
@EnableEurekaServer
public class EurekaServerApplication {

    public static void main(String[] args) {
        SpringApplication.run(EurekaServerApplication.class, args);
    }
}
