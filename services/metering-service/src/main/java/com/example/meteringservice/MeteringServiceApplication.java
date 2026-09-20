package com.example.meteringservice;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.client.discovery.EnableDiscoveryClient;

@SpringBootApplication
@EnableDiscoveryClient
public class MeteringServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(MeteringServiceApplication.class, args);
    }
}
