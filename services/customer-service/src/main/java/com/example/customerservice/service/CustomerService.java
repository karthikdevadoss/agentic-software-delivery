package com.example.customerservice.service;

import com.example.customerservice.model.Customer;
import com.example.customerservice.repository.CustomerRepository;
import org.springframework.stereotype.Service;

import java.util.NoSuchElementException;

@Service
public class CustomerService {

    // Isolated as its own constant, on its own line, mirroring the same
    // deliberate isolation in the monolith's CustomerService -- keeps the
    // human-readable message text as one narrowly-targetable literal,
    // separate from the id suffix appended below.
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

    /** Deliberately email-only: name is not part of this operation's scope. */
    public Customer updateEmail(Long id, String newEmail) {
        Customer customer = getById(id);
        customer.setEmail(newEmail);
        return customerRepository.save(customer);
    }
}
