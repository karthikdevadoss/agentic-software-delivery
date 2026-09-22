package com.example.legacybilling.pricing;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.assertThrows;

/**
 * Contract test for the exact request billing-service's
 * LegacyBillingSystemClient makes:
 *   GET /legacy-billing/plans/{planName}/pricing?customerId={id}
 * and the exact response shape it deserialises (LegacyPlanRateResponse:
 * planName + ratePerKwh). 404 = "plan not in the legacy catalog", which the
 * facade maps to PlanNotRecognized -- so a 404 here is a real, healthy
 * answer, not an error.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class PlanPricingControllerIntegrationTest {

    @LocalServerPort
    private int port;

    private final RestTemplate rest = new RestTemplate();

    private String url(String planName) {
        return "http://localhost:" + port + "/legacy-billing/plans/" + planName + "/pricing?customerId=42";
    }

    @Test
    void residentialFamilyPlanIsPricedFromTheRateCard() {
        ResponseEntity<Map> resp = rest.getForEntity(url("Real-Topology-Residential-abc123"), Map.class);

        assertThat(resp.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(resp.getBody()).containsEntry("planName", "Real-Topology-Residential-abc123");
        assertThat(String.valueOf(resp.getBody().get("ratePerKwh"))).isEqualTo("0.1825");
    }

    @Test
    void unknownPlanFamilyIsA404NotAFabricatedRate() {
        HttpClientErrorException ex = assertThrows(HttpClientErrorException.class,
                () -> rest.getForEntity(url("Mystery-Tariff-9"), Map.class));

        assertThat(ex.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
    }

    @Test
    void missingCustomerIdIsABadRequest() {
        HttpClientErrorException ex = assertThrows(HttpClientErrorException.class,
                () -> rest.getForEntity("http://localhost:" + port + "/legacy-billing/plans/Residential-1/pricing", Map.class));

        assertThat(ex.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
    }
}
