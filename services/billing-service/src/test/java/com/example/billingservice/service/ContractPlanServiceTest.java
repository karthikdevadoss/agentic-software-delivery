package com.example.billingservice.service;

import com.example.billingservice.cache.EnrollmentLockService;
import com.example.billingservice.client.BillingCustomerClient;
import com.example.billingservice.client.CustomerLookupOutcome;
import com.example.billingservice.client.LegacyBillingSystemClient;
import com.example.billingservice.client.LegacyPlanPricingOutcome;
import com.example.billingservice.dto.ContractPlanEnrollRequest;
import com.example.billingservice.exception.CustomerServiceUnavailableException;
import com.example.billingservice.exception.EnrollmentInProgressException;
import com.example.billingservice.exception.LegacyBillingSystemUnavailableException;
import com.example.billingservice.feature.BillingFeature;
import com.example.billingservice.model.ContractPlan;
import com.example.billingservice.model.ContractPlanStatus;
import com.example.billingservice.outbox.OutboxEventRepository;
import com.example.billingservice.repository.ContractPlanRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.togglz.core.manager.FeatureManager;
import tools.jackson.databind.json.JsonMapper;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.NoSuchElementException;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Ported from app/'s ContractPlanServiceTest -- same rigor, same test
 * names/intent where the logic is unchanged. THE FIRST real difference
 * this port made: BillingCustomerClient is mocked directly instead of an
 * in-process CustomerRepository/CustomerService, since billing-service now
 * confirms a customer exists over a real (mocked, here) network call --
 * see ContractPlanService's Javadoc.
 *
 * ACT-013 adds a SECOND: LegacyBillingSystemClient is mocked the same way
 * -- ContractPlanService no longer trusts a caller-submitted rate, it
 * confirms it with this client (see confirmAuthoritativeRate()). Every
 * pre-existing test below stubs it, via {@code service(...)}, to CONFIRM
 * some rate (the specific value is irrelevant to those tests -- none of
 * them assert on the persisted rate); the NEW facade-specific tests below
 * assert on the actual outcome of that call.
 */
@ExtendWith(MockitoExtension.class)
class ContractPlanServiceTest {

    private static final String TEST_BEARER_TOKEN = "Bearer test-token";
    private static final BigDecimal DEFAULT_LEGACY_CONFIRMED_RATE = new BigDecimal("0.9900");

    @Mock
    private ContractPlanRepository contractPlanRepository;
    @Mock
    private BillingCustomerClient billingCustomerClient;
    @Mock
    private LegacyBillingSystemClient legacyBillingSystemClient;
    @Mock
    private OutboxEventRepository outboxEventRepository;
    @Mock
    private EnrollmentLockService enrollmentLockService;
    @Mock
    private FeatureManager featureManager;
    private final JsonMapper jsonMapper = JsonMapper.builder().build();

    private ContractPlanService service(CustomerLookupOutcome lookupOutcome) {
        org.mockito.Mockito.lenient().when(billingCustomerClient.checkCustomerExists(1L, TEST_BEARER_TOKEN)).thenReturn(lookupOutcome);
        // Lenient, same reasoning as lenientLockAcquired() below: not every
        // test path actually reaches confirmAuthoritativeRate() (e.g. the
        // customer-not-found test throws before it), and the specific rate
        // value is irrelevant to every test that stubs via this helper --
        // none of them assert on the persisted rate.
        org.mockito.Mockito.lenient().when(legacyBillingSystemClient.confirmPlanPricing(any(), any(), any()))
                .thenReturn(new LegacyPlanPricingOutcome.Confirmed(DEFAULT_LEGACY_CONFIRMED_RATE));
        // BL-047: real default is "off" -- the legacy system is called normally unless the
        // maintenance-window switch is explicitly flipped, which the one test below does.
        org.mockito.Mockito.lenient().when(featureManager.isActive(BillingFeature.LEGACY_PRICING_BYPASS)).thenReturn(false);
        lenientLockAcquired();
        return newService();
    }

    private ContractPlanService newService() {
        return new ContractPlanService(contractPlanRepository, billingCustomerClient, legacyBillingSystemClient, outboxEventRepository, jsonMapper, enrollmentLockService, featureManager);
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

        assertThatThrownBy(() -> service.enroll(1L, request, TEST_BEARER_TOKEN))
                .isInstanceOf(EnrollmentInProgressException.class);
        verify(contractPlanRepository, org.mockito.Mockito.never()).findByCustomerIdAndStatus(any(), any());
        verify(contractPlanRepository, org.mockito.Mockito.never()).save(any());
        verify(billingCustomerClient, org.mockito.Mockito.never()).checkCustomerExists(any(), any());
        verify(legacyBillingSystemClient, never()).confirmPlanPricing(any(), any(), any());
    }

    @Test
    void enroll_whenCustomerDoesNotExist_throwsBeforeTouchingPlanRepository() {
        ContractPlanService service = service(CustomerLookupOutcome.NOT_FOUND);
        ContractPlanEnrollRequest request = new ContractPlanEnrollRequest("Basic", BigDecimal.TEN, LocalDate.now());

        assertThatThrownBy(() -> service.enroll(1L, request, TEST_BEARER_TOKEN))
                .isInstanceOf(NoSuchElementException.class)
                .hasMessageContaining(ContractPlanService.CUSTOMER_NOT_FOUND_MESSAGE);
        verify(contractPlanRepository, org.mockito.Mockito.never()).findByCustomerIdAndStatus(any(), any());
        // ACT-013: the legacy billing system's (slower, more expensive)
        // pricing lookup must never even be attempted for a customer that
        // was never confirmed to exist.
        verify(legacyBillingSystemClient, never()).confirmPlanPricing(any(), any(), any());
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

        assertThatThrownBy(() -> service.enroll(1L, request, TEST_BEARER_TOKEN))
                .isInstanceOf(CustomerServiceUnavailableException.class);
        verify(contractPlanRepository, org.mockito.Mockito.never()).findByCustomerIdAndStatus(any(), any());
        verify(legacyBillingSystemClient, never()).confirmPlanPricing(any(), any(), any());
    }

    @Test
    void enroll_whenNoExistingActivePlan_createsOneActivePlanOnly() {
        ContractPlanService service = service(CustomerLookupOutcome.FOUND);
        when(contractPlanRepository.findByCustomerIdAndStatus(1L, ContractPlanStatus.ACTIVE)).thenReturn(Optional.empty());
        when(contractPlanRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));
        ContractPlanEnrollRequest request = new ContractPlanEnrollRequest("Basic", new BigDecimal("0.15"), LocalDate.of(2026, 1, 1));

        ContractPlan result = service.enroll(1L, request, TEST_BEARER_TOKEN);

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

        ContractPlan result = service.enroll(1L, request, TEST_BEARER_TOKEN);

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
     *
     * ACT-013 addition: also proves the legacy billing system is NEVER
     * called for this no-op path -- see ContractPlanService.enroll()'s
     * Javadoc comment on confirmAuthoritativeRate()'s placement for why
     * that ordering is deliberate (the legacy system is this flow's slow,
     * expensive dependency; a duplicate submission has no business reason
     * to pay that cost again).
     */
    @Test
    void enroll_whenIdenticalRequestSubmittedTwice_isIdempotentNoOp() {
        ContractPlanService service = service(CustomerLookupOutcome.FOUND);
        ContractPlan alreadyActive = new ContractPlan(1L, "Green Energy 12mo", new BigDecimal("0.1400"), LocalDate.of(2026, 9, 14));
        when(contractPlanRepository.findByCustomerIdAndStatus(1L, ContractPlanStatus.ACTIVE)).thenReturn(Optional.of(alreadyActive));
        ContractPlanEnrollRequest duplicateRequest = new ContractPlanEnrollRequest(
                "Green Energy 12mo", new BigDecimal("0.14"), LocalDate.of(2026, 9, 14));

        ContractPlan result = service.enroll(1L, duplicateRequest, TEST_BEARER_TOKEN);

        assertThat(result).isSameAs(alreadyActive);
        assertThat(result.getStatus()).isEqualTo(ContractPlanStatus.ACTIVE);
        verify(contractPlanRepository, org.mockito.Mockito.never()).saveAndFlush(any());
        verify(contractPlanRepository, org.mockito.Mockito.never()).save(any());
        verify(legacyBillingSystemClient, never()).confirmPlanPricing(any(), any(), any());
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

        service.enroll(1L, request, TEST_BEARER_TOKEN);

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

        service.enroll(1L, request, TEST_BEARER_TOKEN);

        verify(outboxEventRepository, times(1)).save(any());
    }

    /**
     * ACT-013 CORE FACADE BEHAVIOR TEST: the actual point of this whole
     * rework. The caller submits ratePerKwh=0.99 (a bogus/untrusted
     * request); the legacy billing system is stubbed to CONFIRM a
     * completely different rate (0.1550). The PERSISTED plan must carry
     * the legacy-confirmed rate, never the caller-submitted one -- this is
     * exactly the "facade, not owner" distinction ACT-013 exists to prove:
     * before this change, request.ratePerKwh() was trusted outright.
     */
    @Test
    void enroll_usesLegacyBillingSystemsAuthoritativeRate_neverTheCallerSubmittedRate() {
        ContractPlanService service = newService();
        when(billingCustomerClient.checkCustomerExists(1L, TEST_BEARER_TOKEN)).thenReturn(CustomerLookupOutcome.FOUND);
        lenientLockAcquired();
        when(contractPlanRepository.findByCustomerIdAndStatus(1L, ContractPlanStatus.ACTIVE)).thenReturn(Optional.empty());
        when(contractPlanRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));
        BigDecimal legacyConfirmedRate = new BigDecimal("0.1550");
        when(legacyBillingSystemClient.confirmPlanPricing("Basic", 1L, TEST_BEARER_TOKEN))
                .thenReturn(new LegacyPlanPricingOutcome.Confirmed(legacyConfirmedRate));
        ContractPlanEnrollRequest request = new ContractPlanEnrollRequest("Basic", new BigDecimal("0.99"), LocalDate.of(2026, 1, 1));

        ContractPlan result = service.enroll(1L, request, TEST_BEARER_TOKEN);

        assertThat(result.getRatePerKwh()).isEqualByComparingTo(legacyConfirmedRate);
        assertThat(result.getRatePerKwh()).isNotEqualByComparingTo(request.ratePerKwh());
        // Outbound-request-shape proof at the unit level: confirms the
        // legacy client was actually invoked with the real plan name,
        // customer id, and bearer token -- the real end-to-end proof that
        // data is actually sent lives in
        // LegacyBillingSystemClientIntegrationTest (WireMock-backed).
        ArgumentCaptor<String> planNameCaptor = ArgumentCaptor.forClass(String.class);
        verify(legacyBillingSystemClient, times(1)).confirmPlanPricing(planNameCaptor.capture(), org.mockito.ArgumentMatchers.eq(1L), org.mockito.ArgumentMatchers.eq(TEST_BEARER_TOKEN));
        assertThat(planNameCaptor.getValue()).isEqualTo("Basic");
    }

    /**
     * ACT-013: a plan code the legacy billing system's catalog does not
     * recognize is a genuine 404 -- never falls back to the caller-submitted
     * rate, and never mutates any plan state.
     */
    @Test
    void enroll_whenLegacyBillingSystemDoesNotRecognizePlan_throwsBeforeMutatingAnything() {
        ContractPlanService service = newService();
        when(billingCustomerClient.checkCustomerExists(1L, TEST_BEARER_TOKEN)).thenReturn(CustomerLookupOutcome.FOUND);
        lenientLockAcquired();
        when(contractPlanRepository.findByCustomerIdAndStatus(1L, ContractPlanStatus.ACTIVE)).thenReturn(Optional.empty());
        when(legacyBillingSystemClient.confirmPlanPricing("Nonexistent", 1L, TEST_BEARER_TOKEN))
                .thenReturn(new LegacyPlanPricingOutcome.PlanNotRecognized());
        ContractPlanEnrollRequest request = new ContractPlanEnrollRequest("Nonexistent", new BigDecimal("0.20"), LocalDate.of(2026, 1, 1));

        assertThatThrownBy(() -> service.enroll(1L, request, TEST_BEARER_TOKEN))
                .isInstanceOf(NoSuchElementException.class)
                .hasMessageContaining(ContractPlanService.PLAN_NOT_RECOGNIZED_MESSAGE);
        verify(contractPlanRepository, never()).saveAndFlush(any());
        verify(contractPlanRepository, never()).save(any());
        verify(outboxEventRepository, never()).save(any());
    }

    /**
     * ACT-013: the honest, never-fabricated 503 path when
     * LegacyBillingSystemClient genuinely could not reach the legacy
     * system -- distinct from a real "plan not recognized." Mirrors
     * enroll_whenCustomerServiceUnavailable_throwsCustomerServiceUnavailableException
     * exactly, for the new dependency.
     */
    @Test
    void enroll_whenLegacyBillingSystemUnavailable_throwsLegacyBillingSystemUnavailableException() {
        ContractPlanService service = newService();
        when(billingCustomerClient.checkCustomerExists(1L, TEST_BEARER_TOKEN)).thenReturn(CustomerLookupOutcome.FOUND);
        lenientLockAcquired();
        when(contractPlanRepository.findByCustomerIdAndStatus(1L, ContractPlanStatus.ACTIVE)).thenReturn(Optional.empty());
        when(legacyBillingSystemClient.confirmPlanPricing("Basic", 1L, TEST_BEARER_TOKEN))
                .thenReturn(new LegacyPlanPricingOutcome.Unavailable());
        ContractPlanEnrollRequest request = new ContractPlanEnrollRequest("Basic", new BigDecimal("0.20"), LocalDate.of(2026, 1, 1));

        assertThatThrownBy(() -> service.enroll(1L, request, TEST_BEARER_TOKEN))
                .isInstanceOf(LegacyBillingSystemUnavailableException.class);
        verify(contractPlanRepository, never()).saveAndFlush(any());
        verify(contractPlanRepository, never()).save(any());
        verify(outboxEventRepository, never()).save(any());
    }

    /**
     * BL-047: when the real on-call maintenance-window switch is flipped, a new enrollment must
     * fail exactly the same way a real legacy-system timeout would (Unavailable ->
     * LegacyBillingSystemUnavailableException) WITHOUT ever calling the legacy system -- verified
     * here by asserting confirmPlanPricing is never invoked, not just by checking the exception type.
     */
    @Test
    void enroll_whenLegacyPricingBypassActive_throwsWithoutCallingLegacySystem() {
        ContractPlanService service = newService();
        when(billingCustomerClient.checkCustomerExists(1L, TEST_BEARER_TOKEN)).thenReturn(CustomerLookupOutcome.FOUND);
        lenientLockAcquired();
        when(contractPlanRepository.findByCustomerIdAndStatus(1L, ContractPlanStatus.ACTIVE)).thenReturn(Optional.empty());
        when(featureManager.isActive(BillingFeature.LEGACY_PRICING_BYPASS)).thenReturn(true);
        ContractPlanEnrollRequest request = new ContractPlanEnrollRequest("Basic", new BigDecimal("0.20"), LocalDate.of(2026, 1, 1));

        assertThatThrownBy(() -> service.enroll(1L, request, TEST_BEARER_TOKEN))
                .isInstanceOf(LegacyBillingSystemUnavailableException.class);
        verify(legacyBillingSystemClient, never()).confirmPlanPricing(any(), any(), any());
        verify(contractPlanRepository, never()).save(any());
        verify(outboxEventRepository, never()).save(any());
    }
}
