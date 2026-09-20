package com.example.customerservice.security;

import com.example.customerservice.exception.InvalidCredentialsException;
import com.example.customerservice.model.DemoIdentity;
import com.example.customerservice.repository.DemoIdentityRepository;
import jakarta.validation.Valid;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

/**
 * REAL persona login -- distinct from DemoAuthController's anonymous
 * all-scopes token. A username/password pair is genuinely checked
 * server-side against demo_identity (BCrypt hash comparison, role, and
 * enabled state -- never a client-trusted claim), exactly as a real login
 * would be. "Demo" describes the identities (their credentials are
 * intentionally public, see DemoIdentitySeeder), never the verification
 * itself.
 */
@RestController
public class DemoLoginController {

    private final DemoIdentityRepository demoIdentityRepository;
    private final PasswordEncoder passwordEncoder;
    private final DemoJwtIssuer demoJwtIssuer;

    public DemoLoginController(DemoIdentityRepository demoIdentityRepository,
                                PasswordEncoder passwordEncoder,
                                DemoJwtIssuer demoJwtIssuer) {
        this.demoIdentityRepository = demoIdentityRepository;
        this.passwordEncoder = passwordEncoder;
        this.demoJwtIssuer = demoJwtIssuer;
    }

    @PostMapping("/auth/login")
    public DemoLoginResponse login(@Valid @RequestBody DemoLoginRequest request) {
        DemoIdentity identity = demoIdentityRepository.findByUsername(request.username())
                .filter(DemoIdentity::isEnabled)
                .orElseThrow(() -> new InvalidCredentialsException("invalid username or password"));
        if (!passwordEncoder.matches(request.password(), identity.getPasswordHash())) {
            throw new InvalidCredentialsException("invalid username or password");
        }
        String token = demoJwtIssuer.issuePersonaToken(identity);
        return new DemoLoginResponse(
                token, "Bearer", demoJwtIssuer.getDefaultTtl().toSeconds(),
                identity.getUsername(), identity.getRole(), identity.getCustomerId());
    }

    /** Public so a login page's USER/ADMIN dropdowns always reflect the
     * real seeded personas -- never a hardcoded frontend list. */
    @GetMapping("/auth/personas")
    public DemoPersonasResponse personas() {
        return new DemoPersonasResponse(
                demoIdentityRepository.findByRoleOrderByUsernameAsc("USER").stream().map(DemoIdentity::getUsername).toList(),
                demoIdentityRepository.findByRoleOrderByUsernameAsc("ADMIN").stream().map(DemoIdentity::getUsername).toList());
    }
}
