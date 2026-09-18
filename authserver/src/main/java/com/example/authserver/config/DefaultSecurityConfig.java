package com.example.authserver.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.security.authentication.dao.DaoAuthenticationProvider;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;

/**
 * The Authorization Server's OWN login page (/login) -- a real Spring
 * Security form-login flow, authenticating against the SAME BCrypt-hashed
 * demo_identity data the Customer App's own (now-legacy) login flow used,
 * via the SAME real password-verification mechanism (BCryptPasswordEncoder,
 * never a plaintext comparison).
 *
 * This is deliberately the ONE place the demo persona picker lives going
 * forward: a real OAuth2 relying-party's job is to redirect an
 * unauthenticated user to its Authorization Server, not to know how that
 * AS wants to authenticate someone -- exactly why an IdP's own login page,
 * not the relying-party app's, is where a "pick a demo account" UI
 * belongs.
 */
@Configuration
public class DefaultSecurityConfig {

    @Bean
    @Order(2)
    public SecurityFilterChain defaultSecurityFilterChain(HttpSecurity http) throws Exception {
        http
                .authorizeHttpRequests((authorize) -> authorize
                        .requestMatchers("/actuator/health/**", "/actuator/info").permitAll()
                        .anyRequest().authenticated())
                .formLogin(Customizer.withDefaults());
        return http.build();
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    public DaoAuthenticationProvider authenticationProvider(
            UserDetailsService userDetailsService, PasswordEncoder passwordEncoder) {
        DaoAuthenticationProvider provider = new DaoAuthenticationProvider(userDetailsService);
        provider.setPasswordEncoder(passwordEncoder);
        return provider;
    }
}
