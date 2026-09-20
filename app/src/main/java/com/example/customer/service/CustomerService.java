package com.example.customer.service;

import com.example.customer.exception.DuplicateEmailException;
import com.example.customer.model.Customer;
import com.example.customer.repository.CustomerRepository;
import org.springframework.stereotype.Service;

import java.util.NoSuchElementException;

@Service
public class CustomerService {

    // Isolated as its own constant, on its own line, specifically so a
    // future controlled backend Workbench scenario (see ACT-008,
    // docs/ACTION_QUEUE.json) can target ONLY this one string literal
    // via a narrow regex anchor -- exactly analogous to
    // agent/demo_catalogue.py's HTML anchor-pattern operations, applied
    // to Java source instead of static HTML. The id suffix stays
    // separate (appended below) so this constant holds only the
    // human-readable message text.
    static final String CUSTOMER_NOT_FOUND_MESSAGE = "Customer not found";

    private final CustomerRepository customerRepository;

    public CustomerService(CustomerRepository customerRepository) {
        this.customerRepository = customerRepository;
    }

    public Customer getById(Long id) {
        return customerRepository.findById(id)
                .orElseThrow(() -> new NoSuchElementException(CUSTOMER_NOT_FOUND_MESSAGE + ": " + id));
    }

    public Customer create(Customer customer) {
        return customerRepository.save(customer);
    }

    /** REAL IMPLEMENTATION (this was the project's original, long-deferred
     * first ticket -- "Update Email"). Deliberately email-only: name is
     * not part of this operation's scope. Uniqueness added 2026-09-20
     * (BL-013): the original implementation let a customer take over
     * another customer's email address with no rejection at all -- a
     * real gap against the ticket's own acceptance contract, not just a
     * hardening afterthought. */
    public Customer updateEmail(Long id, String newEmail) {
        Customer customer = getById(id);
        if (customerRepository.existsByEmailAndIdNot(newEmail, id)) {
            throw new DuplicateEmailException("Email already in use: " + newEmail);
        }
        customer.setEmail(newEmail);
        return customerRepository.save(customer);
    }
}
