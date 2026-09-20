package com.example.customerservice.mapper;

import com.example.customerservice.dto.CustomerPreferenceResponse;
import com.example.customerservice.model.CustomerPreference;
import com.example.customerservice.model.NotificationChannel;
import org.junit.jupiter.api.Test;
import org.mapstruct.factory.Mappers;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

/**
 * BL-037: real coverage for this codebase's first MapStruct mapper.
 * Uses {@code Mappers.getMapper(...)} directly (not Spring context) so
 * this is a fast, isolated unit test against the real generated
 * implementation -- {@link CustomerPreferenceControllerIntegrationTest}
 * separately covers the Spring-wired path end to end.
 */
class CustomerPreferenceMapperTest {

    private final CustomerPreferenceMapper mapper = Mappers.getMapper(CustomerPreferenceMapper.class);

    @Test
    void maps_every_real_field_correctly() {
        CustomerPreference preference = new CustomerPreference(42L, true, NotificationChannel.SMS);

        CustomerPreferenceResponse response = mapper.toResponse(preference);

        assertEquals(preference.getCustomerId(), response.customerId());
        assertEquals(preference.isPaperlessBilling(), response.paperlessBilling());
        assertEquals(preference.getNotificationChannel(), response.notificationChannel());
        assertEquals(preference.getUpdatedAt(), response.updatedAt());
    }

    @Test
    void null_entity_maps_to_null_not_a_null_pointer_exception() {
        assertNull(mapper.toResponse(null));
    }

    @Test
    void a_real_mismatch_would_actually_be_caught() {
        // Deliberately proves this test isn't vacuous: a genuinely different
        // preference produces a genuinely different, correctly-mapped
        // response -- not the same object reference, not stale/cached values.
        CustomerPreference a = new CustomerPreference(1L, false, NotificationChannel.NONE);
        CustomerPreference b = new CustomerPreference(2L, true, NotificationChannel.EMAIL);

        CustomerPreferenceResponse responseA = mapper.toResponse(a);
        CustomerPreferenceResponse responseB = mapper.toResponse(b);

        assertEquals(1L, responseA.customerId());
        assertEquals(2L, responseB.customerId());
        assertEquals(NotificationChannel.NONE, responseA.notificationChannel());
        assertEquals(NotificationChannel.EMAIL, responseB.notificationChannel());
    }
}
