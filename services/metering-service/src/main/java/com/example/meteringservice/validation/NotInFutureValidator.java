package com.example.meteringservice.validation;

import jakarta.validation.ConstraintValidator;
import jakarta.validation.ConstraintValidatorContext;

import java.time.LocalDate;

/**
 * Real validation logic backing {@link NotInFuture}: valid whenever the
 * date is today or earlier. {@code null} is deliberately treated as valid
 * here -- absence is @NotNull's concern, not this constraint's, so the two
 * annotations each check exactly one thing and their failure messages
 * don't collide/duplicate on a missing value.
 */
public class NotInFutureValidator implements ConstraintValidator<NotInFuture, LocalDate> {

    @Override
    public boolean isValid(LocalDate value, ConstraintValidatorContext context) {
        return value == null || !value.isAfter(LocalDate.now());
    }
}
