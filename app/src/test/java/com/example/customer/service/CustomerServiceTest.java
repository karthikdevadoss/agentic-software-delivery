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
 * Real unit tests for CustomerService's actual behavior, including
 * updateEmail() -- the project's original, long-deferred "Update Email"
 * ticket, finally implemented.
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
    void getById_whenCustomerDoesNotExist_usesTheConstantNotAHardcodedDuplicate() {
        when(customerRepository.findById(999L)).thenReturn(Optional.empty());

        CustomerService service = new CustomerService(customerRepository);

        assertThatThrownBy(() -> service.getById(999L))
                .isInstanceOf(NoSuchElementException.class)
                .hasMessage(CustomerService.CUSTOMER_NOT_FOUND_MESSAGE + ": 999");
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

    @Test
    void updateEmail_whenCustomerExists_changesEmailAndPersists() {
        Customer stored = new Customer("Grace Hopper", "old@example.com");
        stored.setId(1L);
        when(customerRepository.findById(1L)).thenReturn(Optional.of(stored));
        when(customerRepository.save(stored)).thenReturn(stored);

        CustomerService service = new CustomerService(customerRepository);
        Customer result = service.updateEmail(1L, "new@example.com");

        assertThat(result.getEmail()).isEqualTo("new@example.com");
        assertThat(result.getName()).isEqualTo("Grace Hopper"); // unchanged -- email-only operation
        verify(customerRepository).save(stored);
    }

    @Test
    void updateEmail_whenCustomerDoesNotExist_throws404StyleException() {
        when(customerRepository.findById(999L)).thenReturn(Optional.empty());

        CustomerService service = new CustomerService(customerRepository);

        assertThatThrownBy(() -> service.updateEmail(999L, "new@example.com"))
                .isInstanceOf(NoSuchElementException.class)
                .hasMessageContaining("999");
    }

    @Test
    void updateEmail_whenAnotherCustomerAlreadyHasThatEmail_throwsDuplicateEmailException() {
        Customer stored = new Customer("Grace Hopper", "old@example.com");
        stored.setId(1L);
        when(customerRepository.findById(1L)).thenReturn(Optional.of(stored));
        when(customerRepository.existsByEmailAndIdNot("taken@example.com", 1L)).thenReturn(true);

        CustomerService service = new CustomerService(customerRepository);

        assertThatThrownBy(() -> service.updateEmail(1L, "taken@example.com"))
                .isInstanceOf(com.example.customer.exception.DuplicateEmailException.class)
                .hasMessageContaining("taken@example.com");
        verify(customerRepository, org.mockito.Mockito.never()).save(stored);
    }

    @Test
    void updateEmail_reSubmittingOwnCurrentEmail_isNotTreatedAsADuplicate() {
        Customer stored = new Customer("Grace Hopper", "same@example.com");
        stored.setId(1L);
        when(customerRepository.findById(1L)).thenReturn(Optional.of(stored));
        when(customerRepository.existsByEmailAndIdNot("same@example.com", 1L)).thenReturn(false);
        when(customerRepository.save(stored)).thenReturn(stored);

        CustomerService service = new CustomerService(customerRepository);
        Customer result = service.updateEmail(1L, "same@example.com");

        assertThat(result.getEmail()).isEqualTo("same@example.com");
    }
}
