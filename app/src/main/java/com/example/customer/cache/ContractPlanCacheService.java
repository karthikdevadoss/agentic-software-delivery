package com.example.customer.cache;

import com.example.customer.dto.ContractPlanResponse;
import com.example.customer.service.ContractPlanService;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Component;
import tools.jackson.databind.json.JsonMapper;

import java.time.Duration;

/**
 * Cache-aside read caching for a customer's active contract plan --
 * chosen because it is read far more often (every customer-overview page
 * load) than it changes (only on enroll()), a real, motivated business
 * scenario rather than a decorative cache.
 *
 * Deliberately programmatic, not @Cacheable: this makes hit/miss/
 * fallback/invalidation each an explicit, individually testable code
 * path rather than annotation-driven behavior, matching this project's
 * existing preference (see AppointmentAvailabilityConfig's Resilience4j
 * comment) for explicit composition where the exact behavior matters.
 *
 * REDIS-UNAVAILABLE BEHAVIOR: every Redis operation is wrapped -- a read
 * failure falls through to the database (the API never breaks because an
 * optional cache is down); a write/eviction failure is logged and
 * swallowed (the request that triggered it already succeeded against the
 * database, which is the source of truth). This is proven live in real
 * production today: no Redis instance is actually provisioned there yet
 * (a deliberate scope decision -- see docs/ACTION_QUEUE.json), so every
 * production read currently takes the real fallback path, not a
 * simulated one.
 */
@Component
public class ContractPlanCacheService {

    private static final Logger log = LoggerFactory.getLogger(ContractPlanCacheService.class);
    private static final String KEY_PREFIX = "contract-plan:active:";
    private static final Duration TTL = Duration.ofSeconds(60);

    private final RedisTemplate<String, String> redisTemplate;
    private final ContractPlanService contractPlanService;
    private final JsonMapper jsonMapper;
    private final Counter hits;
    private final Counter misses;
    private final Counter redisUnavailable;

    public ContractPlanCacheService(
            RedisTemplate<String, String> redisTemplate,
            ContractPlanService contractPlanService,
            JsonMapper jsonMapper,
            MeterRegistry meterRegistry) {
        this.redisTemplate = redisTemplate;
        this.contractPlanService = contractPlanService;
        this.jsonMapper = jsonMapper;
        this.hits = Counter.builder("cache.requests").tag("cache", "active-plan").tag("result", "hit").register(meterRegistry);
        this.misses = Counter.builder("cache.requests").tag("cache", "active-plan").tag("result", "miss").register(meterRegistry);
        this.redisUnavailable = Counter.builder("cache.requests").tag("cache", "active-plan").tag("result", "redis-unavailable").register(meterRegistry);
    }

    public ContractPlanResponse getActivePlan(Long customerId) {
        String key = KEY_PREFIX + customerId;
        String cachedJson = tryGet(key);
        if (cachedJson != null) {
            hits.increment();
            return jsonMapper.readValue(cachedJson, ContractPlanResponse.class);
        }

        misses.increment();
        // Not wrapped in try/catch: a genuine "no active plan"/"customer
        // not found" 404 must propagate exactly as it does for an
        // uncached read -- caching must never change API error behavior.
        ContractPlanResponse fresh = ContractPlanResponse.from(contractPlanService.getActivePlan(customerId));
        tryPut(key, fresh);
        return fresh;
    }

    /** Called after a successful enroll() so a stale plan is never served past its next real change. */
    public void evict(Long customerId) {
        try {
            redisTemplate.delete(KEY_PREFIX + customerId);
        } catch (Exception redisDown) {
            log.warn("Redis unavailable while evicting active-plan cache for customer {}; a stale entry may be served until its TTL expires", customerId, redisDown);
        }
    }

    private String tryGet(String key) {
        try {
            return redisTemplate.opsForValue().get(key);
        } catch (Exception redisDown) {
            redisUnavailable.increment();
            log.warn("Redis unavailable for active-plan cache read; falling back to the database directly", redisDown);
            return null;
        }
    }

    private void tryPut(String key, ContractPlanResponse value) {
        try {
            redisTemplate.opsForValue().set(key, jsonMapper.writeValueAsString(value), TTL);
        } catch (Exception redisDown) {
            log.warn("Redis unavailable for active-plan cache write; the database read that just succeeded is unaffected", redisDown);
        }
    }
}
