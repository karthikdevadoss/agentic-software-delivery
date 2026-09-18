package com.example.authserver.identity;

import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;

@Service
public class DemoUserDetailsService implements UserDetailsService {

    private final DemoIdentityRepository repository;

    public DemoUserDetailsService(DemoIdentityRepository repository) {
        this.repository = repository;
    }

    @Override
    public UserDetails loadUserByUsername(String username) throws UsernameNotFoundException {
        DemoIdentity identity = repository.findByUsername(username)
                .orElseThrow(() -> new UsernameNotFoundException("No demo identity for username: " + username));
        return new DemoUserDetails(identity);
    }
}
