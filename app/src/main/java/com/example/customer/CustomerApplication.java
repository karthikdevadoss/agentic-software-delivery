package com.example.customer;

import com.example.customer.model.Customer;
import com.example.customer.repository.CustomerRepository;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;

@SpringBootApplication
public class CustomerApplication {

    public static void main(String[] args) {
        SpringApplication.run(CustomerApplication.class, args);
    }

    @Bean
    CommandLineRunner seedData(CustomerRepository customerRepository) {
        return args -> customerRepository.save(new Customer("Ada Lovelace", "ada@example.com"));
    }
}
