package com.example.customer.cache;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.serializer.StringRedisSerializer;

/**
 * Plain String key/value RedisTemplate -- values are serialized manually
 * to/from JSON by ContractPlanCacheService using this project's own
 * autoconfigured Jackson 3 JsonMapper (tools.jackson, see
 * spring-boot-starter-jackson), NOT Spring Data Redis's
 * GenericJackson2JsonRedisSerializer. That class is built against classic
 * Jackson 2 (com.fasterxml.jackson.databind); this project's real JSON
 * provider is Jackson 3 (confirmed via `mvn dependency:tree` -- classic
 * Jackson 2 databind is present only transitively via springdoc/swagger's
 * own internal use, not this app's actual serialization path). Relying on
 * that incidental transitive dependency for real cache serialization
 * would be fragile -- a future springdoc removal could silently break it.
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
