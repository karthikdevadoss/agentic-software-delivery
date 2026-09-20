package com.example.customerservice.controller;

import com.example.customerservice.dto.CustomerPreferenceUpdateRequest;
import com.example.customerservice.model.Customer;
import com.example.customerservice.model.NotificationChannel;
import com.example.customerservice.security.DemoJwtIssuer;
import com.example.customerservice.testsupport.AuthTestSupport;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** Same real-embedded-server + real-H2 + plain RestTemplate pattern as
 * CustomerControllerIntegrationTest (MockMvc is not on this Spring Boot
 * 4.1.1 project's classpath -- see that class's Javadoc for why). */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class CustomerPreferenceControllerIntegrationTest {

    @LocalServerPort
    private int port;

    @Autowired
    private DemoJwtIssuer demoJwtIssuer;

    private RestTemplate restTemplate;

    @BeforeEach
    void setUpAuthenticatedClient() {
        restTemplate = AuthTestSupport.authenticatedRestTemplate(demoJwtIssuer);
    }

    private String url(String path) {
        return "http://localhost:" + port + path;
    }

    private Long createCustomer() {
        Customer created = restTemplate.postForObject(
                url("/customers"), new Customer("Pref Tester", "pref@example.com"), Customer.class);
        return created.getId();
    }

    @Test
    void getPreferences_forCustomerWithNoPreferencesYet_returnsDefaults() {
        Long id = createCustomer();

        ResponseEntity<Map> response = restTemplate.getForEntity(url("/customers/" + id + "/preferences"), Map.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody().get("paperlessBilling")).isEqualTo(false);
        assertThat(response.getBody().get("notificationChannel")).isEqualTo("EMAIL");
    }

    @Test
    void getPreferences_forNonExistentCustomer_returns404() {
        assertThatThrownBy(() -> restTemplate.getForEntity(url("/customers/999999999/preferences"), Map.class))
                .isInstanceOf(HttpClientErrorException.NotFound.class);
    }

    @Test
    void updatePreferences_persistsAndIsReturnedOnSubsequentGet() {
        Long id = createCustomer();
        CustomerPreferenceUpdateRequest update = new CustomerPreferenceUpdateRequest(true, NotificationChannel.SMS);

        restTemplate.put(url("/customers/" + id + "/preferences"), update);
        ResponseEntity<Map> response = restTemplate.getForEntity(url("/customers/" + id + "/preferences"), Map.class);

        assertThat(response.getBody().get("paperlessBilling")).isEqualTo(true);
        assertThat(response.getBody().get("notificationChannel")).isEqualTo("SMS");
    }

    @Test
    void updatePreferences_withNullNotificationChannel_returns400() {
        Long id = createCustomer();
        Map<String, Object> invalidBody = new java.util.LinkedHashMap<>();
        invalidBody.put("paperlessBilling", true);
        invalidBody.put("notificationChannel", null);

        assertThatThrownBy(() -> restTemplate.put(url("/customers/" + id + "/preferences"), invalidBody))
                .isInstanceOf(HttpClientErrorException.BadRequest.class);
    }
}
