package com.example.customerservice.security;

import java.util.List;

/** Public (unauthenticated) list of available demo usernames, split by
 * role, so a login page's dropdown always reflects the real seeded
 * personas rather than a hardcoded frontend list that could silently
 * drift from what the backend actually created. */
public record DemoPersonasResponse(List<String> user, List<String> admin) {
}
