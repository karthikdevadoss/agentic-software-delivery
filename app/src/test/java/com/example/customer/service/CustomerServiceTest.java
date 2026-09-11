package com.example.customer.service;

import com.example.customer.model.Customer;
import com.example.customer.repository.CustomerRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.NoSuchElementException;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Real unit tests for the only business logic this Customer app
 * currently has: CustomerService's real, existing behavior — not a
 * future Update Email feature, not validation/duplicate-handling that
 * isn't implemented yet (see agent/web_server.py's TESTING — NOT
 * CONFIGURED reasoning for why this test file's existence matters).
 */
@ExtendWith(MockitoExtension.class)
class CustomerServiceTest {

    @Mock
    private CustomerRepository customerRepository;

    @Test
    void getById_whenCustomerExists_returnsIt() {
        Customer stored = new Customer("Grace Hopper", "grace@example.com");
        stored.setId(1L);
        when(customerRepository.findById(1L)).thenReturn(Optional.of(stored));

        CustomerService service = new CustomerService(customerRepository);
        Customer result = service.getById(1L);

        assertThat(result.getId()).isEqualTo(1L);
        assertThat(result.getName()).isEqualTo("Grace Hopper");
        assertThat(result.getEmail()).isEqualTo("grace@example.com");
    }

    @Test
    void getById_whenCustomerDoesNotExist_throwsNoSuchElementException() {
        when(customerRepository.findById(999L)).thenReturn(Optional.empty());

        CustomerService service = new CustomerService(customerRepository);

        assertThatThrownBy(() -> service.getById(999L))
                .isInstanceOf(NoSuchElementException.class)
                .hasMessageContaining("999");
    }

    @Test
    void create_delegatesToRepositorySaveAndReturnsItsResult() {
        Customer toSave = new Customer("Ada Lovelace", "ada@example.com");
        Customer saved = new Customer("Ada Lovelace", "ada@example.com");
        saved.setId(42L);
        when(customerRepository.save(toSave)).thenReturn(saved);

        CustomerService service = new CustomerService(customerRepository);
        Customer result = service.create(toSave);

        assertThat(result.getId()).isEqualTo(42L);
        verify(customerRepository).save(toSave);
    }
}
