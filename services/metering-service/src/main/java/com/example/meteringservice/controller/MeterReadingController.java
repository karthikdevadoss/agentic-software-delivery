package com.example.meteringservice.controller;

import com.example.meteringservice.dto.MeterReadingRequest;
import com.example.meteringservice.dto.MeterReadingResponse;
import com.example.meteringservice.dto.UsageSummaryResponse;
import com.example.meteringservice.security.WorkspaceAccessGuard;
import com.example.meteringservice.service.MeterReadingService;
import jakarta.validation.Valid;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.util.List;

@RestController
public class MeterReadingController {

    private final MeterReadingService meterReadingService;
    private final WorkspaceAccessGuard workspaceAccessGuard;

    public MeterReadingController(MeterReadingService meterReadingService, WorkspaceAccessGuard workspaceAccessGuard) {
        this.meterReadingService = meterReadingService;
        this.workspaceAccessGuard = workspaceAccessGuard;
    }

    @PostMapping("/customers/{customerId}/meter-readings")
    public ResponseEntity<MeterReadingResponse> submitReading(
            @PathVariable Long customerId,
            @Valid @RequestBody MeterReadingRequest request,
            @AuthenticationPrincipal Jwt jwt) {
        workspaceAccessGuard.assertAccessible(customerId, jwt);
        MeterReadingResponse response = MeterReadingResponse.from(
                meterReadingService.submitReading(customerId, request));
        return ResponseEntity.status(HttpStatus.CREATED).body(response);
    }

    @GetMapping("/customers/{customerId}/meter-readings")
    public List<MeterReadingResponse> getHistory(
            @PathVariable Long customerId,
            @AuthenticationPrincipal Jwt jwt) {
        workspaceAccessGuard.assertAccessible(customerId, jwt);
        return meterReadingService.getHistory(customerId).stream()
                .map(MeterReadingResponse::from)
                .toList();
    }

    @GetMapping("/customers/{customerId}/usage-summary")
    public UsageSummaryResponse getUsageSummary(
            @PathVariable Long customerId,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate from,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate to,
            @AuthenticationPrincipal Jwt jwt) {
        workspaceAccessGuard.assertAccessible(customerId, jwt);
        return meterReadingService.getUsageSummary(customerId, from, to);
    }
}
