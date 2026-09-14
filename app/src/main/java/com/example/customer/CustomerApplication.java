package com.example.customer;

import com.example.customer.model.Customer;
import com.example.customer.repository.CustomerRepository;
import io.swagger.v3.oas.annotations.enums.SecuritySchemeIn;
import io.swagger.v3.oas.annotations.enums.SecuritySchemeType;
import io.swagger.v3.oas.annotations.security.SecurityScheme;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

/**
 * SecurityScheme documents the real contract now that Spring Security
 * protects the business endpoints (see security/SecurityConfig) -- get a
 * token from POST /auth/demo-token, then authorize with it here or via
 * "Authorize" in Swagger UI. Without this annotation, springdoc has no
 * way to know a JWT is required; it does not infer it from the
 * SecurityFilterChain automatically.
 */
@SecurityScheme(
        name = "bearerAuth",
        type = SecuritySchemeType.HTTP,
        scheme = "bearer",
        bearerFormat = "JWT",
        in = SecuritySchemeIn.HEADER,
        description = "Get a short-lived demo token from POST /auth/demo-token (public, no login required)")
@SpringBootApplication
public class CustomerApplication {

    public static void main(String[] args) {
        SpringApplication.run(CustomerApplication.class, args);
    }

    @Bean
    CommandLineRunner seedData(CustomerRepository customerRepository) {
        return args -> customerRepository.save(new Customer("Ada Lovelace", "ada@example.com"));
    }
}
