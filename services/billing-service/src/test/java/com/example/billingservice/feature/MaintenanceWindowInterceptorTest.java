package com.example.billingservice.feature;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.togglz.core.manager.FeatureManager;

import java.io.PrintWriter;
import java.io.StringWriter;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * BL-073: real, focused coverage of both modes -- normal operation (writes proceed, header still
 * present so a fronting gateway always knows the real state) and an active maintenance window
 * (writes get a real 503 + Retry-After, reads still proceed).
 */
@ExtendWith(MockitoExtension.class)
class MaintenanceWindowInterceptorTest {

    @Mock
    private FeatureManager featureManager;

    private MaintenanceWindowInterceptor interceptor() {
        return new MaintenanceWindowInterceptor(featureManager);
    }

    @Test
    void preHandle_whenNotInMaintenance_allowsWritesAndSetsHeaderFalse() throws Exception {
        when(featureManager.isActive(BillingFeature.MAINTENANCE_WINDOW)).thenReturn(false);
        HttpServletRequest request = mock(HttpServletRequest.class);
        HttpServletResponse response = mock(HttpServletResponse.class);
        // No getMethod() stub needed: when the window isn't active, preHandle returns before ever
        // checking the method -- asserting that short-circuit IS this test's point (see the
        // never(setStatus) assertion below), not an oversight.

        boolean proceed = interceptor().preHandle(request, response, new Object());

        assertThat(proceed).isTrue();
        verify(response).setHeader(MaintenanceWindowInterceptor.MAINTENANCE_HEADER, "false");
        verify(response, org.mockito.Mockito.never()).setStatus(HttpServletResponse.SC_SERVICE_UNAVAILABLE);
    }

    @Test
    void preHandle_whenInMaintenance_blocksWriteWith503AndRetryAfter() throws Exception {
        when(featureManager.isActive(BillingFeature.MAINTENANCE_WINDOW)).thenReturn(true);
        HttpServletRequest request = mock(HttpServletRequest.class);
        HttpServletResponse response = mock(HttpServletResponse.class);
        when(request.getMethod()).thenReturn("POST");
        StringWriter body = new StringWriter();
        when(response.getWriter()).thenReturn(new PrintWriter(body));

        boolean proceed = interceptor().preHandle(request, response, new Object());

        assertThat(proceed).isFalse();
        verify(response).setStatus(HttpServletResponse.SC_SERVICE_UNAVAILABLE);
        verify(response).setHeader("Retry-After", "300");
        verify(response).setHeader(MaintenanceWindowInterceptor.MAINTENANCE_HEADER, "true");
        assertThat(body.toString()).contains("maintenance window");
    }

    @Test
    void preHandle_whenInMaintenance_stillAllowsReads() throws Exception {
        when(featureManager.isActive(BillingFeature.MAINTENANCE_WINDOW)).thenReturn(true);
        HttpServletRequest request = mock(HttpServletRequest.class);
        HttpServletResponse response = mock(HttpServletResponse.class);
        when(request.getMethod()).thenReturn("GET");

        boolean proceed = interceptor().preHandle(request, response, new Object());

        assertThat(proceed).isTrue();
        verify(response, org.mockito.Mockito.never()).setStatus(HttpServletResponse.SC_SERVICE_UNAVAILABLE);
        verify(response).setHeader(MaintenanceWindowInterceptor.MAINTENANCE_HEADER, "true");
    }
}
