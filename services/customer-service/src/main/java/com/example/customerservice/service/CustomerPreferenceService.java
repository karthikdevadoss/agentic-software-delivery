package com.example.customerservice.service;

import com.example.customerservice.model.CustomerPreference;
import com.example.customerservice.model.NotificationChannel;
import com.example.customerservice.repository.CustomerPreferenceRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * BUSINESS REQUIREMENT: a recruiter/customer viewing their profile must
 * always see a preference state, never a "not configured" gap -- even a
 * customer who never touched their settings has an implicit default
 * (paperless billing off, email notifications).
 *
 * DESIGN DECISION: lazily create the default preference row on first read
 * rather than eagerly provisioning one inside CustomerService.create().
 * This keeps CustomerService single-purpose and keeps the two concerns --
 * "a customer exists" and "a customer has preferences" -- independently
 * evolvable.
 *
 * NO OUTBOX HERE, unlike the monolith's CustomerPreferenceService: this
 * service has no OutboxEvent table and no Kafka dependency (see
 * docs/MICROSERVICES_ARCHITECTURE.md -- customer-service issues tokens
 * and owns identity/preference data, it does not fan preference changes
 * out to other services in this decomposition). A preference update here
 * is a plain JPA write, nothing more.
 */
@Service
public class CustomerPreferenceService {

    static final boolean DEFAULT_PAPERLESS_BILLING = false;
    static final NotificationChannel DEFAULT_NOTIFICATION_CHANNEL = NotificationChannel.EMAIL;

    private final CustomerPreferenceRepository preferenceRepository;
    private final CustomerService customerService;

    public CustomerPreferenceService(
            CustomerPreferenceRepository preferenceRepository,
            CustomerService customerService) {
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
