package com.example.billingservice.feature;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.web.servlet.HandlerInterceptor;
import org.togglz.core.manager.FeatureManager;

/**
 * BL-073: the real NRG "SAP monthly maintenance window" pattern (see
 * coaching record: "SAP maintenance-window shutdowns... every second
 * Saturday"). Runs as a Spring MVC interceptor -- AFTER Spring Security's
 * filter chain has already authenticated/authorized the request -- so it
 * never interferes with, or duplicates, the security decision; it only
 * decides whether an already-authorized request may proceed given the
 * current operational mode. Every response carries the maintenance-window
 * state as a header regardless of outcome, so a fronting gateway/aggregator
 * can surface a banner even on requests that succeeded (reads keep working
 * during the window).
 */
public class MaintenanceWindowInterceptor implements HandlerInterceptor {

    public static final String MAINTENANCE_HEADER = "X-Maintenance-Window";
    private static final String RETRY_AFTER_SECONDS = "300";

    private final FeatureManager featureManager;

    public MaintenanceWindowInterceptor(FeatureManager featureManager) {
        this.featureManager = featureManager;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        boolean active = featureManager.isActive(BillingFeature.MAINTENANCE_WINDOW);
        response.setHeader(MAINTENANCE_HEADER, Boolean.toString(active));
        if (!active) {
            return true;
        }
        if (isWriteMethod(request.getMethod())) {
            response.setStatus(HttpServletResponse.SC_SERVICE_UNAVAILABLE);
            response.setHeader("Retry-After", RETRY_AFTER_SECONDS);
            response.setContentType(MediaType.APPLICATION_JSON_VALUE);
            response.getWriter().write(
                    "{\"error\":\"billing-service is in a scheduled maintenance window -- reads remain "
                            + "available, writes are temporarily disabled, please retry later\"}");
            return false;
        }
        return true;
    }

    private static boolean isWriteMethod(String method) {
        return HttpMethod.POST.matches(method)
                || HttpMethod.PUT.matches(method)
                || HttpMethod.PATCH.matches(method)
                || HttpMethod.DELETE.matches(method);
    }
}
