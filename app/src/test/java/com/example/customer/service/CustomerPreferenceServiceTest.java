package com.example.customer.service;

import com.example.customer.model.CustomerPreference;
import com.example.customer.model.NotificationChannel;
import com.example.customer.repository.CustomerPreferenceRepository;
import com.example.customer.repository.CustomerRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.NoSuchElementException;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class CustomerPreferenceServiceTest {

    @Mock
    private CustomerPreferenceRepository preferenceRepository;
    @Mock
    private CustomerRepository customerRepository;

    private CustomerPreferenceService service(com.example.customer.model.Customer existingCustomer) {
        when(customerRepository.findById(1L)).thenReturn(Optional.ofNullable(existingCustomer));
        CustomerService customerService = new CustomerService(customerRepository);
        return new CustomerPreferenceService(preferenceRepository, customerService);
    }

    @Test
    void getOrCreateDefault_whenCustomerDoesNotExist_throws404StyleException() {
        CustomerPreferenceService service = service(null);

        assertThatThrownBy(() -> service.getOrCreateDefault(1L))
                .isInstanceOf(NoSuchElementException.class);
        verify(preferenceRepository, never()).findByCustomerId(any());
    }

    @Test
    void getOrCreateDefault_whenNoPreferenceExists_createsDefaultAndPersistsIt() {
        com.example.customer.model.Customer customer = new com.example.customer.model.Customer("A", "a@example.com");
        customer.setId(1L);
        CustomerPreferenceService service = service(customer);
        when(preferenceRepository.findByCustomerId(1L)).thenReturn(Optional.empty());
        when(preferenceRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));

        CustomerPreference result = service.getOrCreateDefault(1L);

        assertThat(result.isPaperlessBilling()).isEqualTo(CustomerPreferenceService.DEFAULT_PAPERLESS_BILLING);
        assertThat(result.getNotificationChannel()).isEqualTo(CustomerPreferenceService.DEFAULT_NOTIFICATION_CHANNEL);
        verify(preferenceRepository, times(1)).save(any());
    }

    @Test
    void getOrCreateDefault_whenPreferenceAlreadyExists_returnsItWithoutCreatingANewOne() {
        com.example.customer.model.Customer customer = new com.example.customer.model.Customer("A", "a@example.com");
        customer.setId(1L);
        CustomerPreferenceService service = service(customer);
        CustomerPreference existing = new CustomerPreference(1L, true, NotificationChannel.SMS);
        when(preferenceRepository.findByCustomerId(1L)).thenReturn(Optional.of(existing));

        CustomerPreference result = service.getOrCreateDefault(1L);

        assertThat(result).isSameAs(existing);
        verify(preferenceRepository, never()).save(any());
    }

    @Test
    void update_changesBothFieldsAndPersists() {
        com.example.customer.model.Customer customer = new com.example.customer.model.Customer("A", "a@example.com");
        customer.setId(1L);
        CustomerPreferenceService service = service(customer);
        CustomerPreference existing = new CustomerPreference(1L, false, NotificationChannel.EMAIL);
        when(preferenceRepository.findByCustomerId(1L)).thenReturn(Optional.of(existing));
        when(preferenceRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));

        CustomerPreference result = service.update(1L, true, NotificationChannel.SMS);

        assertThat(result.isPaperlessBilling()).isTrue();
        assertThat(result.getNotificationChannel()).isEqualTo(NotificationChannel.SMS);
    }
}
