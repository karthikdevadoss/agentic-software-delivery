package com.example.meteringservice.validation;

import jakarta.validation.Constraint;
import jakarta.validation.Payload;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Real, purpose-built constraint for MeterReadingRequest.readingDate: a
 * meter cannot physically have been read on a date that hasn't happened
 * yet. Written as a custom constraint (rather than reusing Bean
 * Validation's built-in {@code @PastOrPresent}) so this exact business
 * rule -- and its exact wording -- is explicit and independently testable
 * in this service's own validation layer, not implied by a generic
 * date-comparison annotation whose default message doesn't name the
 * domain concept ("reading date").
 */
@Target({ElementType.FIELD, ElementType.PARAMETER, ElementType.RECORD_COMPONENT})
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = NotInFutureValidator.class)
public @interface NotInFuture {

    String message() default "readingDate must not be in the future";

    Class<?>[] groups() default {};

    Class<? extends Payload>[] payload() default {};
}
