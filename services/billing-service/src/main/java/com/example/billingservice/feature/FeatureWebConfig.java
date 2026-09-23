package com.example.billingservice.feature;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;
import org.togglz.core.manager.FeatureManager;

/** Registers MaintenanceWindowInterceptor -- excludes the Togglz console itself and actuator health,
 * so the maintenance window can always be inspected/toggled even while active, and health checks
 * never report unhealthy just because writes are paused. */
@Configuration
public class FeatureWebConfig implements WebMvcConfigurer {

    private final FeatureManager featureManager;

    public FeatureWebConfig(FeatureManager featureManager) {
        this.featureManager = featureManager;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(new MaintenanceWindowInterceptor(featureManager))
                .excludePathPatterns("/togglz/**", "/actuator/**");
    }
}
