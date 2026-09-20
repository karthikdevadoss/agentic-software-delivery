package com.example.customerservice.security;

public record DemoLoginResponse(
        String accessToken,
        String tokenType,
        long expiresInSeconds,
        String username,
        String role,
        Long customerId) {
}
