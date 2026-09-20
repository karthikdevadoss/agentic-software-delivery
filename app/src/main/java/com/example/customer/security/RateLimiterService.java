package com.example.customer.security;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Component;

import java.time.Duration;

/**
 * FIXED-WINDOW rate limiter, Redis INCR+EXPIRE -- the simplest correct
 * building block, chosen deliberately over a sliding-window/token-bucket
 * algorithm for this scope: real, well-known trade-off worth being
 * explicit about rather than silently picking one. Fixed-window is O(1)
 * per request (one INCR, one conditional EXPIRE) and exactly correct
 * WITHIN a window, but allows up to 2x the nominal limit across a window
 * boundary (e.g. a burst at 0:59 and another at 1:00 of a 60s window both
 * see a fresh counter). That is an accepted, understood limitation here --
 * a token-bucket or sliding-window-log algorithm closes it at the cost of
 * more Redis round-trips/state, a real thing to weigh against actual abuse
 * patterns rather than reach for reflexively.
 *
 * FAILS OPEN, same philosophy as ContractPlanCacheService and
 * EnrollmentLockService: if Redis is unreachable, every request is
 * allowed rather than the API becoming unavailable because an optional
 * protection layer is down. A rate limiter that fails closed would turn
 * "Redis had a blip" into "the whole public demo is down" -- a strictly
 * worse outcome for a portfolio demo than occasionally under-protecting
 * an endpoint for the (rare, already-proven-safe-by-two-other-features)
 * duration of a real Redis outage.
 */
@Component
public class RateLimiterService {

    private static final Logger log = LoggerFactory.getLogger(RateLimiterService.class);
    private static final String KEY_PREFIX = "rate-limit:";

    private final RedisTemplate<String, String> redisTemplate;
    private final Counter allowed;
    private final Counter rejected;
    private final Counter redisUnavailable;

    public RateLimiterService(RedisTemplate<String, String> redisTemplate, MeterRegistry meterRegistry) {
        this.redisTemplate = redisTemplate;
        this.allowed = Counter.builder("rate_limiter.requests").tag("result", "allowed").register(meterRegistry);
        this.rejected = Counter.builder("rate_limiter.requests").tag("result", "rejected").register(meterRegistry);
        this.redisUnavailable = Counter.builder("rate_limiter.requests").tag("result", "redis-unavailable-failed-open").register(meterRegistry);
    }

    /** @param bucket a namespace for the thing being limited (e.g. "demo-token"), so different endpoints never share a counter
     *  @param clientKey the caller identity to limit by (e.g. client IP for an unauthenticated endpoint)
     *  @return true if this request is allowed to proceed */
    public boolean allow(String bucket, String clientKey, int limit, Duration window) {
        String key = KEY_PREFIX + bucket + ":" + clientKey;
        try {
            Long count = redisTemplate.opsForValue().increment(key);
            if (count != null && count == 1L) {
                redisTemplate.expire(key, window); // only the request that started this window sets its TTL
            }
            boolean withinLimit = count != null && count <= limit;
            (withinLimit ? allowed : rejected).increment();
            return withinLimit;
        } catch (Exception redisDown) {
            redisUnavailable.increment();
            log.warn("Redis unavailable for rate limiting bucket '{}'; failing open (request allowed)", bucket, redisDown);
            return true;
        }
    }
}
