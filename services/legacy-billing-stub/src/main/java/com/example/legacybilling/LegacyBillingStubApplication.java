package com.example.legacybilling;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * BL-038: the "legacy billing system" the billing-service facade confirms
 * plan rates with. In the Owner's real NRG platform this hop was an
 * integration endpoint in front of SAP (SOAP via NRGWS / the SPEC
 * services); here it is a small, honest stand-in with a fixed rate card,
 * reached at a fixed URL (legacy-billing-system.base-url), never through
 * service discovery -- exactly the shape ACT-013 documented and the
 * real-topology harness was missing (ACT-015).
 */
@SpringBootApplication
public class LegacyBillingStubApplication {

    public static void main(String[] args) {
        SpringApplication.run(LegacyBillingStubApplication.class, args);
    }
}
