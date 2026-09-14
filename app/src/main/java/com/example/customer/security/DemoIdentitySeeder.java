package com.example.customer.security;

import com.example.customer.model.Customer;
import com.example.customer.model.DemoIdentity;
import com.example.customer.repository.CustomerRepository;
import com.example.customer.repository.DemoIdentityRepository;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

/**
 * Seeds the fixed set of PORTFOLIO DEMO login identities (3 USER personas,
 * each bound to its own real, distinct Customer row/workspace, and 2
 * ADMIN personas with no customer binding) exactly once, idempotently
 * (guarded by demo_identity's own row count -- never re-seeds or
 * duplicates on every restart). The password hash is generated at seed
 * time via the real injected {@link PasswordEncoder} bean, the exact same
 * encoder {@link DemoLoginController} later verifies against -- never a
 * hand-computed/hardcoded hash that could silently drift from what the
 * encoder actually produces.
 *
 * The shared demo password is intentionally public (see
 * {@link #DEMO_PASSWORD}'s Javadoc) -- this is explicit portfolio-demo
 * authentication, not a security gap: no identity here can ever be
 * granted anything beyond DemoJwtIssuer.DEMO_SCOPES (+ ADMIN_SCOPES for
 * the 2 admin personas).
 */
@Component
public class DemoIdentitySeeder implements ApplicationRunner {

    /** Publicly known by design -- the login UI prefills it (see the
     * "FRICTIONLESS REAL DEMO LOGIN" requirement). Never used for any
     * non-demo identity or account. */
    public static final String DEMO_PASSWORD = "Demo@123";

    private final DemoIdentityRepository demoIdentityRepository;
    private final CustomerRepository customerRepository;
    private final PasswordEncoder passwordEncoder;

    public DemoIdentitySeeder(DemoIdentityRepository demoIdentityRepository,
                               CustomerRepository customerRepository,
                               PasswordEncoder passwordEncoder) {
        this.demoIdentityRepository = demoIdentityRepository;
        this.customerRepository = customerRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @Override
    public void run(ApplicationArguments args) {
        if (demoIdentityRepository.count() > 0) {
            return; // already seeded -- idempotent, never duplicates on restart/redeploy
        }
        seedUser("user1", "user1@energydemo.local", "Alex Rivera");
        seedUser("user2", "user2@energydemo.local", "Jordan Lee");
        seedUser("user3", "user3@energydemo.local", "Sam Patel");
        seedAdmin("admin1");
        seedAdmin("admin2");
    }

    private void seedUser(String username, String email, String name) {
        Customer customer = customerRepository.save(new Customer(name, email));
        DemoIdentity identity = new DemoIdentity();
        identity.setUsername(username);
        identity.setPasswordHash(passwordEncoder.encode(DEMO_PASSWORD));
        identity.setRole("USER");
        identity.setWorkspaceId("ws-" + username);
        identity.setCustomerId(customer.getId());
        identity.setEnabled(true);
        demoIdentityRepository.save(identity);
    }

    private void seedAdmin(String username) {
        DemoIdentity identity = new DemoIdentity();
        identity.setUsername(username);
        identity.setPasswordHash(passwordEncoder.encode(DEMO_PASSWORD));
        identity.setRole("ADMIN");
        identity.setWorkspaceId("ws-" + username);
        identity.setCustomerId(null);
        identity.setEnabled(true);
        demoIdentityRepository.save(identity);
    }
}
