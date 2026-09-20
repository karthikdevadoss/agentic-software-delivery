package com.example.billingservice.service;

import com.example.billingservice.cache.EnrollmentLockService;
import com.example.billingservice.client.BillingCustomerClient;
import com.example.billingservice.client.CustomerLookupOutcome;
import com.example.billingservice.dto.ContractPlanEnrollRequest;
import com.example.billingservice.exception.CustomerServiceUnavailableException;
import com.example.billingservice.exception.EnrollmentInProgressException;
import com.example.billingservice.model.ContractPlan;
import com.example.billingservice.model.ContractPlanStatus;
import com.example.billingservice.outbox.OutboxEventRepository;
import com.example.billingservice.repository.ContractPlanRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import tools.jackson.databind.json.JsonMapper;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.NoSuchElementException;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Ported from app/'s ContractPlanServiceTest -- same rigor, same test
 * names/intent where the logic is unchanged. THE ONE REAL DIFFERENCE (the
 * point of this port): BillingCustomerClient is mocked directly instead of
 * an in-process CustomerRepository/CustomerService, since billing-service
 * now confirms a customer exists over a real (mocked, here) network call
 * -- see ContractPlanService's Javadoc.
 */
@ExtendWith(MockitoExtension.class)
class ContractPlanServiceTest {

    @Mock
    private ContractPlanRepository contractPlanRepository;
    @Mock
    private BillingCustomerClient billingCustomerClient;
    @Mock
    private OutboxEventRepository outboxEventRepository;
    @Mock
    private EnrollmentLockService enrollmentLockService;
    private final JsonMapper jsonMapper = JsonMapper.builder().build();

    private ContractPlanService service(CustomerLookupOutcome lookupOutcome) {
        org.mockito.Mockito.lenient().when(billingCustomerClient.checkCustomerExists(1L)).thenReturn(lookupOutcome);
        lenientLockAcquired();
        return newService();
    }

    private ContractPlanService newService() {
        return new ContractPlanService(contractPlanRepository, billingCustomerClient, outboxEventRepository, jsonMapper, enrollmentLockService);
    }

    /** Default every test to "lock acquired" (real Redis behavior for the
     * normal, uncontended case) unless a test overrides it -- lenient
     * because not every test path actually calls tryAcquire's stubbed
     * return value (e.g. the customer-not-found test still acquires the
     * lock before the 404 check runs). */
    private void lenientLockAcquired() {
        org.mockito.Mockito.lenient().when(enrollmentLockService.tryAcquire(1L))
                .thenReturn(new EnrollmentLockService.LockResult.Acquired("test-token"));
    }

    @Test
    void getActivePlan_whenNoneExists_throwsWithClearMessage() {
        when(contractPlanRepository.findByCustomerIdAndStatus(1L, ContractPlanStatus.ACTIVE)).thenReturn(Optional.empty());
        ContractPlanService service = newService();

        assertThatThrownBy(() -> service.getActivePlan(1L))
                .isInstanceOf(NoSuchElementException.class)
                .hasMessageContaining(ContractPlanService.NO_ACTIVE_PLAN_MESSAGE);
    }

    /**
     * Regression test for the real "raw 500 under concurrency" gap the
     * Redis lock closes: when a second request for the same customer
     * loses the lock race, it must fail FAST and CLEANLY with
     * EnrollmentInProgressException (mapped to 409, see
     * GlobalExceptionHandler) -- never reaching the repository or
     * customer-service at all.
     */
    @Test
    void enroll_whenLockNotAcquired_throwsCleanlyWithoutTouchingPlanRepositoryOrCustomerService() {
        // Deliberately no billingCustomerClient stub: the lock check
        // happens BEFORE the customer-existence lookup, so asserting that
        // never happens either is part of what this test proves.
        when(enrollmentLockService.tryAcquire(1L)).thenReturn(new EnrollmentLockService.LockResult.NotAcquired());
        ContractPlanService service = newService();
        ContractPlanEnrollRequest request = new ContractPlanEnrollRequest("Basic", BigDecimal.TEN, LocalDate.now());

        assertThatThrownBy(() -> service.enroll(1L, request))
                .isInstanceOf(EnrollmentInProgressException.class);
        verify(contractPlanRepository, org.mockito.Mockito.never()).findByCustomerIdAndStatus(any(), any());
        verify(contractPlanRepository, org.mockito.Mockito.never()).save(any());
        verify(billingCustomerClient, org.mockito.Mockito.never()).checkCustomerExists(any());
    }

    @Test
    void enroll_whenCustomerDoesNotExist_throwsBeforeTouchingPlanRepository() {
        ContractPlanService service = service(CustomerLookupOutcome.NOT_FOUND);
        ContractPlanEnrollRequest request = new ContractPlanEnrollRequest("Basic", BigDecimal.TEN, LocalDate.now());

        assertThatThrownBy(() -> service.enroll(1L, request))
                .isInstanceOf(NoSuchElementException.class)
                .hasMessageContaining(ContractPlanService.CUSTOMER_NOT_FOUND_MESSAGE);
        verify(contractPlanRepository, org.mockito.Mockito.never()).findByCustomerIdAndStatus(any(), any());
    }

    /**
     * NEW test (no monolith equivalent -- customer-service could never be
     * "unreachable" for an in-process call): confirms the honest,
     * never-fabricated 503 path when BillingCustomerClient genuinely could
     * not reach customer-service -- distinct from a real 404.
     */
    @Test
    void enroll_whenCustomerServiceUnavailable_throwsCustomerServiceUnavailableException() {
        ContractPlanService service = service(CustomerLookupOutcome.SERVICE_UNAVAILABLE);
        ContractPlanEnrollRequest request = new ContractPlanEnrollRequest("Basic", BigDecimal.TEN, LocalDate.now());

        assertThatThrownBy(() -> service.enroll(1L, request))
                .isInstanceOf(CustomerServiceUnavailableException.class);
        verify(contractPlanRepository, org.mockito.Mockito.never()).findByCustomerIdAndStatus(any(), any());
    }

    @Test
    void enroll_whenNoExistingActivePlan_createsOneActivePlanOnly() {
        ContractPlanService service = service(CustomerLookupOutcome.FOUND);
        when(contractPlanRepository.findByCustomerIdAndStatus(1L, ContractPlanStatus.ACTIVE)).thenReturn(Optional.empty());
        when(contractPlanRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));
        ContractPlanEnrollRequest request = new ContractPlanEnrollRequest("Basic", new BigDecimal("0.15"), LocalDate.of(2026, 1, 1));

        ContractPlan result = service.enroll(1L, request);

        assertThat(result.getStatus()).isEqualTo(ContractPlanStatus.ACTIVE);
        assertThat(result.getPlanName()).isEqualTo("Basic");
        verify(contractPlanRepository, times(1)).save(any());
    }

    @Test
    void enroll_whenActivePlanAlreadyExists_cancelsItBeforeCreatingTheNewOne() {
        ContractPlanService service = service(CustomerLookupOutcome.FOUND);
        ContractPlan oldPlan = new ContractPlan(1L, "Old", new BigDecimal("0.20"), LocalDate.of(2025, 1, 1));
        when(contractPlanRepository.findByCustomerIdAndStatus(1L, ContractPlanStatus.ACTIVE)).thenReturn(Optional.of(oldPlan));
        when(contractPlanRepository.saveAndFlush(any())).thenAnswer(inv -> inv.getArgument(0));
        when(contractPlanRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));
        LocalDate newStart = LocalDate.of(2026, 6, 1);
        ContractPlanEnrollRequest request = new ContractPlanEnrollRequest("New", new BigDecimal("0.12"), newStart);

        ContractPlan result = service.enroll(1L, request);

        ArgumentCaptor<ContractPlan> flushedCaptor = ArgumentCaptor.forClass(ContractPlan.class);
        verify(contractPlanRepository, times(1)).saveAndFlush(flushedCaptor.capture());
        ContractPlan cancelledPlan = flushedCaptor.getValue();
        assertThat(cancelledPlan).isSameAs(oldPlan);
        assertThat(cancelledPlan.getStatus()).isEqualTo(ContractPlanStatus.CANCELLED);
        assertThat(cancelledPlan.getEffectiveEndDate()).isEqualTo(newStart);
        assertThat(result.getStatus()).isEqualTo(ContractPlanStatus.ACTIVE);
        assertThat(result.getPlanName()).isEqualTo("New");
    }

    /**
     * IDEMPOTENCY regression test, ported from app/: submitting the exact
     * same enrollment twice (e.g. a double-click, or a client retry after
     * a timeout whose original call had actually succeeded) must be a
     * true no-op: the existing active plan is returned unchanged, and
     * neither saveAndFlush() (cancel) nor save() (create) is ever called.
     */
    @Test
    void enroll_whenIdenticalRequestSubmittedTwice_isIdempotentNoOp() {
        ContractPlanService service = service(CustomerLookupOutcome.FOUND);
        ContractPlan alreadyActive = new ContractPlan(1L, "Green Energy 12mo", new BigDecimal("0.1400"), LocalDate.of(2026, 9, 14));
        when(contractPlanRepository.findByCustomerIdAndStatus(1L, ContractPlanStatus.ACTIVE)).thenReturn(Optional.of(alreadyActive));
        ContractPlanEnrollRequest duplicateRequest = new ContractPlanEnrollRequest(
                "Green Energy 12mo", new BigDecimal("0.14"), LocalDate.of(2026, 9, 14));

        ContractPlan result = service.enroll(1L, duplicateRequest);

        assertThat(result).isSameAs(alreadyActive);
        assertThat(result.getStatus()).isEqualTo(ContractPlanStatus.ACTIVE);
        verify(contractPlanRepository, org.mockito.Mockito.never()).saveAndFlush(any());
        verify(contractPlanRepository, org.mockito.Mockito.never()).save(any());
    }

    /**
     * Regression test for a real bug caught ONLY by a genuine Postgres
     * Testcontainers run in the monolith (see app/'s LESSONS.md): plain
     * save() on the cancelled plan let the new plan's INSERT reach the
     * database first, briefly creating two ACTIVE rows. This test locks in
     * the fix: the cancellation MUST use saveAndFlush(), never plain
     * save(), specifically so the UPDATE is forced to the database before
     * the new INSERT is even issued.
     */
    @Test
    void enroll_whenActivePlanAlreadyExists_flushesTheCancellationBeforeInsertingTheNewPlan() {
        ContractPlanService service = service(CustomerLookupOutcome.FOUND);
        ContractPlan oldPlan = new ContractPlan(1L, "Old", new BigDecimal("0.20"), LocalDate.of(2025, 1, 1));
        when(contractPlanRepository.findByCustomerIdAndStatus(1L, ContractPlanStatus.ACTIVE)).thenReturn(Optional.of(oldPlan));
        when(contractPlanRepository.saveAndFlush(any())).thenAnswer(inv -> inv.getArgument(0));
        when(contractPlanRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));
        ContractPlanEnrollRequest request = new ContractPlanEnrollRequest("New", new BigDecimal("0.12"), LocalDate.of(2026, 6, 1));

        service.enroll(1L, request);

        org.mockito.InOrder order = org.mockito.Mockito.inOrder(contractPlanRepository);
        order.verify(contractPlanRepository).saveAndFlush(oldPlan);
        order.verify(contractPlanRepository).save(org.mockito.ArgumentMatchers.argThat(
                p -> p.getStatus() == ContractPlanStatus.ACTIVE && p.getPlanName().equals("New")));
    }

    @Test
    void enroll_writesAnOutboxEventOnlyForARealNewEnrollment() {
        ContractPlanService service = service(CustomerLookupOutcome.FOUND);
        when(contractPlanRepository.findByCustomerIdAndStatus(1L, ContractPlanStatus.ACTIVE)).thenReturn(Optional.empty());
        when(contractPlanRepository.save(any())).thenAnswer(inv -> {
            ContractPlan plan = inv.getArgument(0);
            return plan;
        });
        ContractPlanEnrollRequest request = new ContractPlanEnrollRequest("Basic", new BigDecimal("0.15"), LocalDate.of(2026, 1, 1));

        service.enroll(1L, request);

        verify(outboxEventRepository, times(1)).save(any());
    }
}
