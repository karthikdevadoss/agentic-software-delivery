package com.example.customerservice.security;

import jakarta.validation.constraints.NotBlank;

public record DemoLoginRequest(@NotBlank String username, @NotBlank String password) {
}
