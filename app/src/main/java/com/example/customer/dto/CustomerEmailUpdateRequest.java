package com.example.customer.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;

public record CustomerEmailUpdateRequest(
        @NotBlank(message = "email must not be blank")
        @Email(message = "email must be a well-formed email address") String email
) {
}
