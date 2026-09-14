package com.example.customer.service;

import com.example.customer.event.CustomerPreferenceUpdatedEvent;
import com.example.customer.model.CustomerPreference;
import com.example.customer.model.NotificationChannel;
import com.example.customer.outbox.OutboxEvent;
import com.example.customer.outbox.OutboxEventRepository;
import com.example.customer.repository.CustomerPreferenceRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.json.JsonMapper;

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

    private static final String AGGREGATE_TYPE = "CustomerPreference";
    private static final String EVENT_TYPE = "CustomerPreferenceUpdated";

    private final CustomerPreferenceRepository preferenceRepository;
    private final CustomerService customerService;
    private final OutboxEventRepository outboxEventRepository;
    private final JsonMapper jsonMapper;

    public CustomerPreferenceService(
            CustomerPreferenceRepository preferenceRepository,
            CustomerService customerService,
            OutboxEventRepository outboxEventRepository,
            JsonMapper jsonMapper) {
        this.preferenceRepository = preferenceRepository;
        this.customerService = customerService;
        this.outboxEventRepository = outboxEventRepository;
        this.jsonMapper = jsonMapper;
    }

    @Transactional
    public CustomerPreference getOrCreateDefault(Long customerId) {
        customerService.getById(customerId); // 404s (NoSuchElementException) if the customer itself does not exist
        return preferenceRepository.findByCustomerId(customerId)
                .orElseGet(() -> preferenceRepository.save(
                        new CustomerPreference(customerId, DEFAULT_PAPERLESS_BILLING, DEFAULT_NOTIFICATION_CHANNEL)));
    }

    /**
     * TRANSACTIONAL OUTBOX, not a naive dual write: the preference update
     * and its outbox event row are both plain JPA writes inside this ONE
     * @Transactional method, so they commit or roll back together. Kafka
     * itself is never touched here -- OutboxPublisher polls and publishes
     * unpublished rows asynchronously, so a slow/unavailable Kafka broker
     * can never fail or block this request.
     */
    @Transactional
    public CustomerPreference update(Long customerId, boolean paperlessBilling, NotificationChannel notificationChannel) {
        CustomerPreference preference = getOrCreateDefault(customerId);
        preference.update(paperlessBilling, notificationChannel);
        CustomerPreference saved = preferenceRepository.save(preference);

        CustomerPreferenceUpdatedEvent event = new CustomerPreferenceUpdatedEvent(
                customerId, saved.isPaperlessBilling(), saved.getNotificationChannel(), saved.getUpdatedAt());
        outboxEventRepository.save(new OutboxEvent(
                AGGREGATE_TYPE, customerId, EVENT_TYPE, jsonMapper.writeValueAsString(event)));

        return saved;
    }
}
