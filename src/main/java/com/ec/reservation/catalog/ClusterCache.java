package com.ec.reservation.catalog;

import java.time.Duration;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

@Service
public class ClusterCache {
    private final StringRedisTemplate redis;
    ClusterCache(StringRedisTemplate redis) { this.redis = redis; }

    String version(String country) {
        try {
            String version = redis.opsForValue().get("ec:map:version:" + country);
            return version == null ? "0" : version;
        } catch (RuntimeException error) { return "offline"; }
    }

    String get(String key) {
        try { return redis.opsForValue().get(key); }
        catch (RuntimeException error) { return null; }
    }

    void put(String key, String json) {
        try { redis.opsForValue().set(key, json, Duration.ofMinutes(15)); }
        catch (RuntimeException ignored) { }
    }

    void invalidate(String country) {
        try { redis.opsForValue().increment("ec:map:version:" + country); }
        catch (RuntimeException ignored) { }
    }

    public boolean online() {
        try (var connection = redis.getConnectionFactory().getConnection()) {
            return "PONG".equalsIgnoreCase(connection.ping());
        } catch (RuntimeException error) { return false; }
    }
}
