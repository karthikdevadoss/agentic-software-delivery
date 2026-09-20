package com.example.billingservice.cache;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.serializer.StringRedisSerializer;

/**
 * Plain String key/value RedisTemplate -- values are serialized manually
 * to/from JSON by ContractPlanCacheService using this project's own
 * autoconfigured Jackson 3 JsonMapper (tools.jackson, pulled in
 * transitively via spring-boot-starter-web -- confirmed the same way the
 * monolith confirmed it, see app/'s RedisCacheConfig comment), NOT Spring
 * Data Redis's GenericJackson2JsonRedisSerializer, which is built against
 * classic Jackson 2 (com.fasterxml.jackson.databind) and is not this
 * project's real JSON provider.
 *
 * Ported unchanged from app/'s com.example.customer.cache.RedisCacheConfig.
 */
@Configuration
public class RedisCacheConfig {

    @Bean
    public RedisTemplate<String, String> redisTemplate(RedisConnectionFactory connectionFactory) {
        RedisTemplate<String, String> template = new RedisTemplate<>();
        template.setConnectionFactory(connectionFactory);
        template.setKeySerializer(new StringRedisSerializer());
        template.setValueSerializer(new StringRedisSerializer());
        template.afterPropertiesSet();
        return template;
    }
}
