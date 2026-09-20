package com.example.customerservice.repository;

import com.example.customerservice.model.DemoIdentity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface DemoIdentityRepository extends JpaRepository<DemoIdentity, Long> {
    Optional<DemoIdentity> findByUsername(String username);

    List<DemoIdentity> findByRoleOrderByUsernameAsc(String role);
}
