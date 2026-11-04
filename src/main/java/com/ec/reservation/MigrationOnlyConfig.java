package com.ec.reservation;

import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class MigrationOnlyConfig {
    @Bean
    @ConditionalOnProperty(name = "app.migration-only", havingValue = "true")
    ApplicationRunner exitAfterMigrations(ConfigurableApplicationContext context) {
        return args -> System.exit(SpringApplication.exit(context));
    }
}
