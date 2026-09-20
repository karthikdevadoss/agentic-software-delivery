package com.example.billingservice.tracing;

import brave.Tracing;
import brave.propagation.B3Propagation;
import brave.propagation.CurrentTraceContext;
import brave.propagation.ThreadLocalCurrentTraceContext;
import brave.sampler.Sampler;
import io.micrometer.tracing.brave.bridge.BraveCurrentTraceContext;
import io.micrometer.tracing.brave.bridge.BravePropagator;
import io.micrometer.tracing.brave.bridge.BraveTracer;
import io.micrometer.tracing.propagation.Propagator;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * BL-014: manual Brave wiring, real infra fix, not a workaround.
 *
 * ROOT CAUSE (verified via a live `--debug` Spring Boot condition-evaluation
 * report run against this exact service, plus direct jar inspection of the
 * resolved artifacts): Spring Boot 4.1.1 + micrometer-tracing 1.7.1 +
 * Spring Cloud 2025.1.2 does NOT auto-configure a real Brave-backed
 * io.micrometer.tracing.Tracer bean in this dependency combination.
 * org.springframework.boot.micrometer.tracing.autoconfigure.NoopTracerAutoConfiguration
 * always wins (its @ConditionalOnMissingBean(Tracer.class) finds nothing).
 * The spring-boot-micrometer-tracing-4.1.1.jar module (Boot 4's own
 * modular split of the old spring-boot-actuator-autoconfigure tracing
 * package) ships MicrometerTracingAutoConfiguration + NoopTracerAutoConfiguration
 * only -- no Brave-specific @AutoConfiguration class exists anywhere on
 * this classpath (confirmed by listing every class in that jar and in
 * micrometer-tracing-bridge-brave-1.7.1.jar directly), so
 * micrometer-tracing-bridge-brave being present is necessary but not
 * sufficient: it supplies the real Brave bridge CLASSES, not a Spring
 * bean definition that wires them together.
 *
 * FIX: this is Micrometer Tracing's own documented manual-Brave-setup
 * path -- define the beans that auto-configuration would otherwise have
 * created, by hand, using the real classes resolved on this project's
 * classpath (brave 6.3.1 via micrometer-tracing-bridge-brave 1.7.1,
 * verified by extracting and reading both jars' real class/method
 * signatures with javap before writing this file, per this project's own
 * "never guess an unfamiliar API shape" rule -- an earlier attempt
 * tonight was burned by exactly that mistake elsewhere).
 *
 * Once a real io.micrometer.tracing.Tracer + Propagator bean exist here,
 * Spring Boot's OWN MicrometerTracingAutoConfiguration (already on the
 * classpath, previously inert because it also requires those same beans)
 * activates for real and registers the actual propagating
 * ObservationHandlers (PropagatingSenderTracingObservationHandler /
 * PropagatingReceiverTracingObservationHandler) that inject/extract B3
 * headers on real HTTP client/server calls -- confirmed by reading that
 * class's bytecode directly (javap) rather than assuming. No other
 * manual wiring beyond these 3 beans is required.
 */
@Configuration
public class BraveTracingConfig {

    @Bean
    public CurrentTraceContext braveCurrentTraceContext() {
        return ThreadLocalCurrentTraceContext.newBuilder().build();
    }

    @Bean(destroyMethod = "close")
    public Tracing braveTracing(CurrentTraceContext currentTraceContext,
                                 @Value("${spring.application.name:service}") String serviceName) {
        return Tracing.newBuilder()
                .localServiceName(serviceName)
                .currentTraceContext(currentTraceContext)
                // ALWAYS_SAMPLE deliberately, per this task's own scope: this is
                // a demo/interview-story system, not a production deployment --
                // real production would use a probabilistic/rate-limited sampler.
                .sampler(Sampler.ALWAYS_SAMPLE)
                .propagationFactory(B3Propagation.FACTORY)
                .build();
    }

    @Bean
    public brave.Tracer braveTracer(Tracing braveTracing) {
        return braveTracing.tracer();
    }

    @Bean
    public io.micrometer.tracing.Tracer tracer(brave.Tracer braveTracer, CurrentTraceContext currentTraceContext) {
        return new BraveTracer(braveTracer, BraveCurrentTraceContext.fromBrave(currentTraceContext));
    }

    @Bean
    public Propagator propagator(Tracing braveTracing) {
        return new BravePropagator(braveTracing);
    }
}
