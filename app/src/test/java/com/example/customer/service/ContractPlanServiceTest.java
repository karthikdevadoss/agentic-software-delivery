package com.example.customer.service;

import com.example.customer.dto.ContractPlanEnrollRequest;
import com.example.customer.model.ContractPlan;
import com.example.customer.model.ContractPlanStatus;
import com.example.customer.model.Customer;
import com.example.customer.repository.ContractPlanRepository;
import com.example.customer.repository.CustomerRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

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

@ExtendWith(MockitoExtension.class)
class ContractPlanServiceTest {

    @Mock
    private ContractPlanRepository contractPlanRepository;
    @Mock
    private CustomerRepository customerRepository;

    private ContractPlanService service(Customer existingCustomer) {
        when(customerRepository.findById(1L)).thenReturn(Optional.ofNullable(existingCustomer));
        return new ContractPlanService(contractPlanRepository, new CustomerService(customerRepository));
    }

    private Customer existingCustomer() {
        Customer c = new Customer("A", "a@example.com");
        c.setId(1L);
        return c;
    }

    @Test
    void getActivePlan_whenNoneExists_throwsWithClearMessage() {
        when(contractPlanRepository.findByCustomerIdAndStatus(1L, ContractPlanStatus.ACTIVE)).thenReturn(Optional.empty());
        ContractPlanService service = new ContractPlanService(contractPlanRepository, new CustomerService(customerRepository));

        assertThatThrownBy(() -> service.getActivePlan(1L))
                .isInstanceOf(NoSuchElementException.class)
                .hasMessageContaining(ContractPlanService.NO_ACTIVE_PLAN_MESSAGE);
    }

    @Test
    void enroll_whenCustomerDoesNotExist_throwsBeforeTouchingPlanRepository() {
        ContractPlanService service = service(null);
        ContractPlanEnrollRequest request = new ContractPlanEnrollRequest("Basic", BigDecimal.TEN, LocalDate.now());

        assertThatThrownBy(() -> service.enroll(1L, request)).isInstanceOf(NoSuchElementException.class);
        verify(contractPlanRepository, org.mockito.Mockito.never()).findByCustomerIdAndStatus(any(), any());
    }

    @Test
    void enroll_whenNoExistingActivePlan_createsOneActivePlanOnly() {
        ContractPlanService service = service(existingCustomer());
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
        ContractPlanService service = service(existingCustomer());
        ContractPlan oldPlan = new ContractPlan(1L, "Old", new BigDecimal("0.20"), LocalDate.of(2025, 1, 1));
        when(contractPlanRepository.findByCustomerIdAndStatus(1L, ContractPlanStatus.ACTIVE)).thenReturn(Optional.of(oldPlan));
        when(contractPlanRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));
        LocalDate newStart = LocalDate.of(2026, 6, 1);
        ContractPlanEnrollRequest request = new ContractPlanEnrollRequest("New", new BigDecimal("0.12"), newStart);

        ContractPlan result = service.enroll(1L, request);

        ArgumentCaptor<ContractPlan> savedCaptor = ArgumentCaptor.forClass(ContractPlan.class);
        verify(contractPlanRepository, times(2)).save(savedCaptor.capture());
        ContractPlan firstSaved = savedCaptor.getAllValues().get(0);
        assertThat(firstSaved).isSameAs(oldPlan);
        assertThat(firstSaved.getStatus()).isEqualTo(ContractPlanStatus.CANCELLED);
        assertThat(firstSaved.getEffectiveEndDate()).isEqualTo(newStart);
        assertThat(result.getStatus()).isEqualTo(ContractPlanStatus.ACTIVE);
        assertThat(result.getPlanName()).isEqualTo("New");
    }
}
