package com.example.authserver.identity;

import org.springframework.data.repository.Repository;

import java.util.Optional;

/**
 * {@link Repository}, not {@code JpaRepository} -- deliberately exposes
 * only {@link #findByUsername}, no save/delete methods at all, so there is
 * no code path in this whole service that could ever write to the shared
 * identity table, enforced by the interface's own shape rather than by
 * convention/discipline alone.
 */
public interface DemoIdentityRepository extends Repository<DemoIdentity, Long> {
    Optional<DemoIdentity> findByUsername(String username);
}
