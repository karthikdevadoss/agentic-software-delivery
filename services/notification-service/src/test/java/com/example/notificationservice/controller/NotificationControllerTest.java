package com.example.notificationservice.controller;

import com.example.notificationservice.dto.SendNotificationRequest;
import com.example.notificationservice.dto.SendNotificationResponse;
import com.example.notificationservice.model.NotificationChannel;
import com.example.notificationservice.testsupport.TestJwtSupport;
import io.micrometer.core.instrument.MeterRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestTemplate;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Plain HTTP + service-layer proof of POST /notifications/send -- no
 * Docker/Testcontainers needed (unlike ContractPlanEventFlowIntegrationTest):
 * this is the synchronous direct-trigger path, calling
 * NotificationSenderFactory directly with no Kafka involved at all. Real
 * HTTP calls against a real running SpringBootTest context, real JWTs
 * signed by TestJwtSupport against this service's own configured
 * secret/issuer/audience (see SecurityConfig), and real MeterRegistry
 * counter assertions -- no mocks.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class NotificationControllerTest {

    @LocalServerPort
    private int port;

    @Autowired
    private MeterRegistry meterRegistry;

    @Value("${app.security.jwt.secret}")
    private String jwtSecret;
    @Value("${app.security.jwt.issuer}")
    private String jwtIssuer;
    @Value("${app.security.jwt.audience}")
    private String jwtAudience;

    private RestTemplate authenticatedRestTemplate;

    @BeforeEach
    void setUp() {
        authenticatedRestTemplate = TestJwtSupport.authenticatedRestTemplate(jwtSecret, jwtIssuer, jwtAudience);
    }

    private String url(String path) {
        return "http://localhost:" + port + path;
    }

    @Test
    void sendingAnEmailNotification_realDispatchThroughTheFactory_incrementsTheRealCounter() {
        double before = counterOrZero("EMAIL");

        ResponseEntity<SendNotificationResponse> response = authenticatedRestTemplate.postForEntity(
                url("/notifications/send"),
                new SendNotificationRequest(77L, NotificationChannel.EMAIL, "Your invoice is ready"),
                SendNotificationResponse.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().customerId()).isEqualTo(77L);
        assertThat(response.getBody().channel()).isEqualTo(NotificationChannel.EMAIL);
        assertThat(response.getBody().status()).isEqualTo("dispatched");

        assertThat(counterOrZero("EMAIL")).isEqualTo(before + 1.0);
    }

    @Test
    void sendingAnSmsNotification_realDispatchThroughTheFactory_incrementsTheRealCounter() {
        double before = counterOrZero("SMS");

        ResponseEntity<SendNotificationResponse> response = authenticatedRestTemplate.postForEntity(
                url("/notifications/send"),
                new SendNotificationRequest(78L, NotificationChannel.SMS, "Your meter reading is due"),
                SendNotificationResponse.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(counterOrZero("SMS")).isEqualTo(before + 1.0);
    }

    @Test
    void aBlankMessage_isRejectedWithA400_notSilentlyAccepted() {
        assertThatThrownBy(() -> authenticatedRestTemplate.postForEntity(
                url("/notifications/send"),
                new SendNotificationRequest(79L, NotificationChannel.EMAIL, ""),
                SendNotificationResponse.class))
                .isInstanceOf(HttpClientErrorException.BadRequest.class);
    }

    @Test
    void aRequestWithNoToken_isRejectedWithA401() {
        RestTemplate anonymousRestTemplate = new RestTemplate();

        assertThatThrownBy(() -> anonymousRestTemplate.postForEntity(
                url("/notifications/send"),
                new SendNotificationRequest(80L, NotificationChannel.EMAIL, "hello"),
                SendNotificationResponse.class))
                .isInstanceOf(HttpClientErrorException.Unauthorized.class);
    }

    private double counterOrZero(String channel) {
        var counter = meterRegistry.find("notification.dispatched").tag("channel", channel).counter();
        return counter == null ? 0.0 : counter.count();
    }
}
