package com.example.billingservice.cache;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.List;
import java.util.UUID;

/**
 * DISTRIBUTED LOCK, layered DEFENSE-IN-DEPTH with the existing
 * uq_contract_plan_one_active_per_customer database constraint (see
 * ContractPlanService's Javadoc): the DB constraint is the correctness
 * guarantee that can never be bypassed, but relying on it alone means two
 * genuinely concurrent enroll() requests for the same customer both run
 * their full business logic, and the LOSER surfaces an ugly, unguided
 * database-constraint-violation 500 to its caller. This lock is a FAST,
 * OPTIONAL improvement to that experience: acquire a short-TTL Redis lock
 * before the enroll() critical section; a request that cannot acquire it
 * fails immediately with a clean, actionable 409 ("try again") instead of
 * racing the database. Redis is optional at every step here (same
 * philosophy as ContractPlanCacheService): if it is unreachable, every
 * request proceeds WITHOUT app-level locking, and the DB constraint alone
 * -- already proven correct under a real concurrent-insert race, see
 * ContractPlanService's saveAndFlush comment -- keeps the system correct.
 * The service can never become MORE broken because an optional lock layer
 * is down; it can only lose the nicer 409 experience in favor of the DB's
 * plainer 500 for that one, rare, genuinely-concurrent case.
 *
 * TOKEN-OWNED RELEASE, not a naive SETNX/DEL pair: a lock is released only
 * if the caller presents the exact token it was granted at acquire time
 * (a Lua script makes the GET-compare-DELETE atomic). Without this, a slow
 * request whose lock already expired (past its TTL) could delete a
 * DIFFERENT, later request's now-active lock on the same key when it
 * finally reaches its own release() call -- a real, classic distributed-
 * locking bug class, not a hypothetical.
 *
 * Ported unchanged from app/'s com.example.customer.cache.EnrollmentLockService
 * (see docs/MICROSERVICES_ARCHITECTURE.md) -- this logic does not change
 * between the monolith and this service.
 */
@Component
public class EnrollmentLockService {

    private static final Logger log = LoggerFactory.getLogger(EnrollmentLockService.class);
    private static final String KEY_PREFIX = "enroll-lock:";
    private static final Duration LOCK_TTL = Duration.ofSeconds(10);

    private static final DefaultRedisScript<Long> RELEASE_SCRIPT = new DefaultRedisScript<>(
            "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) else return 0 end",
            Long.class);

    private final RedisTemplate<String, String> redisTemplate;

    public EnrollmentLockService(RedisTemplate<String, String> redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    public sealed interface LockResult {
        record Acquired(String token) implements LockResult {}
        record NotAcquired() implements LockResult {}
        record RedisUnavailable() implements LockResult {}
    }

    public LockResult tryAcquire(Long customerId) {
        String token = UUID.randomUUID().toString();
        try {
            Boolean acquired = redisTemplate.opsForValue().setIfAbsent(KEY_PREFIX + customerId, token, LOCK_TTL);
            if (Boolean.TRUE.equals(acquired)) {
                return new LockResult.Acquired(token);
            }
            return new LockResult.NotAcquired();
        } catch (Exception redisDown) {
            log.warn("Redis unavailable while acquiring enrollment lock for customer {}; proceeding without app-level locking -- the database constraint remains the correctness guarantee", customerId, redisDown);
            return new LockResult.RedisUnavailable();
        }
    }

    public void release(Long customerId, String token) {
        try {
            redisTemplate.execute(RELEASE_SCRIPT, List.of(KEY_PREFIX + customerId), token);
        } catch (Exception redisDown) {
            log.warn("Redis unavailable while releasing enrollment lock for customer {}; it will self-expire after its TTL", customerId, redisDown);
        }
    }
}
