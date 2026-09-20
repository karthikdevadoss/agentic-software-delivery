package com.example.eureka;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.client.RestClient;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

/**
 * ACT-014 / BL-024: the second real proof this service needs -- not just
 * "does the registry app start" (EurekaServerApplicationTests) but "can a
 * real service actually register itself here and be discovered", which is
 * the entire reason this service exists in the microservices decomposition
 * (docs/MICROSERVICES_ARCHITECTURE.md).
 *
 * REAL DESIGN CHOICE, found via this test's own first (failed) attempt:
 * the obvious approach -- boot a second, independent Spring Boot context
 * in-process as a real spring-cloud-netflix-eureka-client and let it
 * register itself the normal way -- hit a genuine spring-cloud-netflix-
 * eureka-client 5.0.2 wiring gap: EurekaAutoServiceRegistration.start()
 * NPEs on EurekaRegistration.getEurekaClient() being null, reproducibly,
 * regardless of WebApplicationType (SERVLET or NONE). This is a real
 * framework friction point when running a second Eureka-client Spring
 * context inside the SAME JVM as the server under test, not a mistake in
 * this test's own setup -- not worth working around with brittle internal
 * API reflection.
 *
 * Instead, this test registers a real instance directly against
 * eureka-server's own real REST registration protocol (POST
 * /eureka/apps/{appId}) -- the EXACT wire protocol every real Eureka
 * client (including every other service in this repo) uses under the
 * hood. Testing at this boundary is a real, faithful proof of "can a
 * service register and be discovered", arguably more direct than coupling
 * this test to spring-cloud-netflix-eureka-client's internal bean wiring,
 * which is a different, already-covered concern (every other service's
 * own successful registration against a real eureka-server in
 * services/real-topology-tests/run_real_topology_test.py's proven runs).
 *
 * The GET-side polling mirrors the bounded, no-fixed-sleep
 * readiness-polling convention run_real_topology_test.py's own
 * wait_for_eureka_registration already established for this exact
 * "registration not immediately visible" race, via Awaitility (the
 * JUnit-idiomatic equivalent of that script's time.monotonic()+sleep
 * loop) rather than asserting immediately after the POST.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class EurekaServerRegistrationIntegrationTest {

    private static final String APP_ID = "TEST-REGISTERING-CLIENT";
    private static final String INSTANCE_ID = "test-registering-client:19999";

    @LocalServerPort
    private int eurekaPort;

    private RestClient restClient;

    @AfterEach
    void deregister() {
        // Real cleanup: deregister the real instance this test registered,
        // via the same real REST protocol, so no test-created instance
        // leaks into another test's view of the registry.
        if (restClient != null) {
            try {
                restClient.delete()
                        .uri(baseAppsUrl() + "/" + APP_ID + "/" + INSTANCE_ID)
                        .retrieve()
                        .toBodilessEntity();
            } catch (Exception ignored) {
                // Best-effort cleanup only -- a failed deregister (e.g. the
                // registration test itself failed before registering)
                // must never mask the real test result.
            }
        }
    }

    private String baseAppsUrl() {
        return "http://localhost:" + eurekaPort + "/eureka/apps";
    }

    @Test
    void aRealServiceCanRegisterWithThisRegistryAndBeDiscovered() {
        restClient = RestClient.create();

        // Real Eureka REST registration payload -- the same shape any real
        // Eureka client (including every other service in this repo) sends
        // over the wire on startup.
        String registrationBody = """
                {
                  "instance": {
                    "instanceId": "%s",
                    "hostName": "localhost",
                    "app": "%s",
                    "ipAddr": "127.0.0.1",
                    "status": "UP",
                    "port": {"$": 19999, "@enabled": "true"},
                    "securePort": {"$": 443, "@enabled": "false"},
                    "dataCenterInfo": {
                      "@class": "com.netflix.appinfo.InstanceInfo$DefaultDataCenterInfo",
                      "name": "MyOwn"
                    }
                  }
                }
                """.formatted(INSTANCE_ID, APP_ID);

        HttpStatus registerStatus = (HttpStatus) restClient.post()
                .uri(baseAppsUrl() + "/" + APP_ID)
                .header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .body(registrationBody)
                .retrieve()
                .toBodilessEntity()
                .getStatusCode();

        // Eureka's real REST contract for a successful registration is 204.
        assertThat(registerStatus).isEqualTo(HttpStatus.NO_CONTENT);

        // Bounded, polling proof of real discoverability -- never a fixed
        // sleep, never a first-try assertion right after the POST (see
        // class Javadoc: registration visibility is not guaranteed
        // synchronous with the 204 response).
        await().atMost(Duration.ofSeconds(15))
                .pollInterval(Duration.ofSeconds(1))
                .untilAsserted(() -> {
                    String body = restClient.get()
                            .uri(baseAppsUrl() + "/" + APP_ID)
                            .header(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                            .retrieve()
                            .body(String.class);
                    assertThat(body).isNotNull();
                    assertThat(body).contains(INSTANCE_ID);
                    assertThat(body).contains("\"status\":\"UP\"");
                });
    }
}
