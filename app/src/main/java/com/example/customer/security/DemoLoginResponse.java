package com.example.customer.security;

public record DemoLoginResponse(
        String accessToken,
        String tokenType,
        long expiresInSeconds,
        String username,
        String role,
        Long customerId) {
}
