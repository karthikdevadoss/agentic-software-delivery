package com.example.customer.security;

import jakarta.validation.constraints.NotBlank;

public record DemoLoginRequest(@NotBlank String username, @NotBlank String password) {
}
