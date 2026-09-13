package com.example.customer.service;

import com.example.customer.model.CustomerPreference;
import com.example.customer.model.NotificationChannel;
import com.example.customer.repository.CustomerPreferenceRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * BUSINESS REQUIREMENT: a recruiter/customer viewing their profile must
 * always see a preference state, never a "not configured" gap — even a
 * customer who never touched their settings has an implicit default
 * (paperless billing off, email notifications).
 *
 * DESIGN DECISION: lazily create the default preference row on first read
 * rather than eagerly provisioning one inside CustomerService.create().
 * This keeps CustomerService single-purpose (it stays untouched by this
 * feature) and keeps the two concerns — "a customer exists" and "a
 * customer has preferences" — independently evolvable.
 */
@Service
public class CustomerPreferenceService {

    static final boolean DEFAULT_PAPERLESS_BILLING = false;
    static final NotificationChannel DEFAULT_NOTIFICATION_CHANNEL = NotificationChannel.EMAIL;

    private final CustomerPreferenceRepository preferenceRepository;
    private final CustomerService customerService;

    public CustomerPreferenceService(CustomerPreferenceRepository preferenceRepository, CustomerService customerService) {
        this.preferenceRepository = preferenceRepository;
        this.customerService = customerService;
    }

    @Transactional
    public CustomerPreference getOrCreateDefault(Long customerId) {
        customerService.getById(customerId); // 404s (NoSuchElementException) if the customer itself does not exist
        return preferenceRepository.findByCustomerId(customerId)
                .orElseGet(() -> preferenceRepository.save(
                        new CustomerPreference(customerId, DEFAULT_PAPERLESS_BILLING, DEFAULT_NOTIFICATION_CHANNEL)));
    }

    @Transactional
    public CustomerPreference update(Long customerId, boolean paperlessBilling, NotificationChannel notificationChannel) {
        CustomerPreference preference = getOrCreateDefault(customerId);
        preference.update(paperlessBilling, notificationChannel);
        return preferenceRepository.save(preference);
    }
}
