package com.example.billingservice.service;

import com.example.billingservice.cache.EnrollmentLockService;
import com.example.billingservice.client.BillingCustomerClient;
import com.example.billingservice.client.CustomerLookupOutcome;
import com.example.billingservice.dto.ContractPlanEnrollRequest;
import com.example.billingservice.event.ContractPlanEnrolledEvent;
import com.example.billingservice.exception.CustomerServiceUnavailableException;
import com.example.billingservice.exception.EnrollmentInProgressException;
import com.example.billingservice.model.ContractPlan;
import com.example.billingservice.model.ContractPlanStatus;
import com.example.billingservice.outbox.OutboxEvent;
import com.example.billingservice.outbox.OutboxEventRepository;
import com.example.billingservice.repository.ContractPlanRepository;
import org.springframework.context.annotation.Lazy;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import tools.jackson.databind.json.JsonMapper;

import java.time.Instant;
import java.util.NoSuchElementException;
import java.util.Optional;

/**
 * BUSINESS REQUIREMENT: a customer has at most one ACTIVE energy plan at a
 * time. Enrolling in a new plan must not silently leave two plans marked
 * ACTIVE (a real data-integrity bug class this test suite specifically
 * checks for) -- the prior active plan is cancelled, end-dated on the new
 * plan's start date, and kept (never deleted) so plan history is queryable.
 *
 * Ported from app/'s com.example.customer.service.ContractPlanService --
 * see this class's Javadoc there for the full original reasoning. THE ONE
 * REAL CHANGE this port makes (the actual point of this microservice
 * exercise, see docs/MICROSERVICES_ARCHITECTURE.md): the monolith's
 * in-process {@code customerService.getById(customerId)} call is replaced
 * with a genuine REST call to customer-service via BillingCustomerClient.
 * Everything else -- the idempotency no-op check, the saveAndFlush-before-
 * insert ordering fix, the Redis lock integration, and the outbox event
 * write -- is unchanged.
 */
@Service
public class ContractPlanService {

    static final String NO_ACTIVE_PLAN_MESSAGE = "No active contract plan found for customer";
    static final String CUSTOMER_NOT_FOUND_MESSAGE = "Customer not found";
    private static final String AGGREGATE_TYPE = "ContractPlan";
    private static final String EVENT_TYPE = "ContractPlanEnrolled";

    private final ContractPlanRepository contractPlanRepository;
    private final BillingCustomerClient billingCustomerClient;
    private final OutboxEventRepository outboxEventRepository;
    private final JsonMapper jsonMapper;
    private final EnrollmentLockService enrollmentLockService;

    public ContractPlanService(
            ContractPlanRepository contractPlanRepository,
            @Lazy BillingCustomerClient billingCustomerClient,
            OutboxEventRepository outboxEventRepository,
            JsonMapper jsonMapper,
            EnrollmentLockService enrollmentLockService) {
        this.contractPlanRepository = contractPlanRepository;
        this.billingCustomerClient = billingCustomerClient;
        this.outboxEventRepository = outboxEventRepository;
        this.jsonMapper = jsonMapper;
        this.enrollmentLockService = enrollmentLockService;
    }

    public ContractPlan getActivePlan(Long customerId) {
        return contractPlanRepository.findByCustomerIdAndStatus(customerId, ContractPlanStatus.ACTIVE)
                .orElseThrow(() -> new NoSuchElementException(NO_ACTIVE_PLAN_MESSAGE + ": " + customerId));
    }

    /**
     * LAYERED CONCURRENCY CONTROL, fast path + last-resort safety net: an
     * app-level Redis lock (see EnrollmentLockService's Javadoc) is
     * acquired FIRST, before any check-then-act business logic runs. A
     * request that loses the race fails fast and cleanly with a 409
     * (EnrollmentInProgressException) instead of racing a concurrent
     * request all the way down to the database, where
     * uq_contract_plan_one_active_per_customer would reject the loser with
     * an unguided 500. The lock is released only AFTER this transaction
     * actually commits (registerLockReleaseAfterTransaction) -- releasing
     * it any earlier (e.g. a plain try/finally around the method body)
     * would reopen the exact race this exists to close: a second request
     * could acquire the freed lock and read "no active plan yet" before
     * the first request's write is durably visible.
     */
    @Transactional
    public ContractPlan enroll(Long customerId, ContractPlanEnrollRequest request, String callerBearerToken) {
        EnrollmentLockService.LockResult lockResult = enrollmentLockService.tryAcquire(customerId);
        if (lockResult instanceof EnrollmentLockService.LockResult.NotAcquired) {
            throw new EnrollmentInProgressException(
                    "Enrollment already in progress for customer " + customerId + " -- please retry");
        }
        if (lockResult instanceof EnrollmentLockService.LockResult.Acquired acquired) {
            registerLockReleaseAfterTransaction(customerId, acquired.token());
        }
        // RedisUnavailable: no lock was taken, nothing to release -- proceed
        // relying solely on the database constraint, exactly as this method
        // always has.

        // REAL CHANGE vs. the monolith: this used to be an in-process
        // customerService.getById(customerId) call. billing-service does
        // not own Customer data (customer-service does), so this is now a
        // genuine network call, honestly distinguishing "customer does not
        // exist" (404) from "we could not find out" (503) -- see
        // CustomerLookupOutcome's Javadoc.
        CustomerLookupOutcome lookup = billingCustomerClient.checkCustomerExists(customerId, callerBearerToken);
        if (lookup == CustomerLookupOutcome.NOT_FOUND) {
            throw new NoSuchElementException(CUSTOMER_NOT_FOUND_MESSAGE + ": " + customerId);
        }
        if (lookup == CustomerLookupOutcome.SERVICE_UNAVAILABLE) {
            throw new CustomerServiceUnavailableException(
                    "customer-service unreachable while verifying customer " + customerId + " -- please retry");
        }

        Optional<ContractPlan> currentlyActive =
                contractPlanRepository.findByCustomerIdAndStatus(customerId, ContractPlanStatus.ACTIVE);

        // IDEMPOTENCY: a duplicate submission of the exact same enrollment
        // (a double-click, or a client retrying after a timeout whose
        // original request actually succeeded server-side) must not be
        // treated as a second business event. Before this check existed, a
        // repeat call cancelled the plan the FIRST call had just activated
        // and created another new plan identical to it -- two CANCELLED
        // rows plus a second ACTIVE row in the customer's plan history for
        // what was really one action, and any future side effect fired on
        // ACTIVE-plan creation (billing, notifications, events) would have
        // double-fired. If the currently active plan already has identical
        // terms to what's being requested, this is a no-op: return it
        // unchanged, touch nothing else.
        if (currentlyActive.filter(existing -> isSameTerms(existing, request)).isPresent()) {
            return currentlyActive.get();
        }

        // REAL BUG found only by a genuine Postgres integration test (H2's
        // ddl-auto schema has no equivalent constraint to violate, so this
        // was invisible there): Hibernate's default flush ORDER executes
        // all pending INSERTs before any pending UPDATEs in a single
        // transaction flush, regardless of the order save() was called in
        // Java code. Using plain save() here let the new plan's INSERT
        // reach Postgres before the old plan's cancellation UPDATE did --
        // for one instant, two ACTIVE rows existed for the same customer,
        // which uq_contract_plan_one_active_per_customer (a real,
        // immediate, non-deferred Postgres constraint) correctly rejected
        // with a 500. saveAndFlush() forces the cancellation to reach the
        // database BEFORE the new row is ever inserted, closing the gap.
        currentlyActive.ifPresent(existing -> {
            existing.cancel(request.effectiveStartDate());
            contractPlanRepository.saveAndFlush(existing);
        });

        ContractPlan newPlan = new ContractPlan(
                customerId, request.planName(), request.ratePerKwh(), request.effectiveStartDate());
        ContractPlan saved = contractPlanRepository.save(newPlan);

        // TRANSACTIONAL OUTBOX, same pattern as the monolith's
        // CustomerPreferenceService.update(): this row commits in the SAME
        // transaction as the plan write, so OutboxPublisher can never
        // publish an enrollment that didn't really happen, and a genuinely
        // committed enrollment can never silently fail to get an event
        // row. The idempotent no-op path above deliberately does NOT reach
        // here -- a duplicate submission of an already-active plan is not
        // a new business event.
        ContractPlanEnrolledEvent event = new ContractPlanEnrolledEvent(
                saved.getId(), customerId, saved.getPlanName(), saved.getRatePerKwh(),
                saved.getEffectiveStartDate(), Instant.now());
        outboxEventRepository.save(new OutboxEvent(
                AGGREGATE_TYPE, saved.getId(), EVENT_TYPE, jsonMapper.writeValueAsString(event)));

        return saved;
    }

    private static boolean isSameTerms(ContractPlan existing, ContractPlanEnrollRequest request) {
        return existing.getPlanName().equals(request.planName())
                && existing.getRatePerKwh().compareTo(request.ratePerKwh()) == 0
                && existing.getEffectiveStartDate().equals(request.effectiveStartDate());
    }

    private void registerLockReleaseAfterTransaction(Long customerId, String token) {
        if (!TransactionSynchronizationManager.isSynchronizationActive()) {
            // Should never happen inside a @Transactional-proxied call, but
            // release immediately rather than leak the lock for its full TTL.
            enrollmentLockService.release(customerId, token);
            return;
        }
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCompletion(int status) {
                enrollmentLockService.release(customerId, token);
            }
        });
    }
}
