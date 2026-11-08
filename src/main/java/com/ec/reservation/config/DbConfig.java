package com.ec.reservation.config;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import javax.sql.DataSource;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;

@Configuration
public class DbConfig {
    @Value("${app.db.primary-host}") private String primaryHost;
    @Value("${app.db.replica-host}") private String replicaHost;
    @Value("${app.db.primary-port}") private int primaryPort;
    @Value("${app.db.replica-port}") private int replicaPort;
    @Value("${app.preview.read-only:false}") private boolean previewReadOnly;
    @Value("${app.preview.db-password:}") private String previewPassword;

    private DataSource source(String host, int port, String user, String password, boolean readOnly) {
        if (previewReadOnly) {
            if (previewPassword.isBlank()) throw new IllegalStateException("PREVIEW_DB_PASSWORD is required in preview mode");
            user = "preview_reader";
            password = previewPassword;
            readOnly = true;
        }
        HikariConfig config = new HikariConfig();
        config.setJdbcUrl("jdbc:postgresql://" + host + ":" + port + "/ec_reservation");
        config.setUsername(user);
        config.setPassword(password);
        config.setMaximumPoolSize(3);
        config.setMinimumIdle(0);
        config.setReadOnly(readOnly);
        config.setInitializationFailTimeout(-1);
        config.setPoolName(user + (readOnly ? "-read" : "-write"));
        return new HikariDataSource(config);
    }

    @Bean("identityDataSource")
    DataSource identityDataSource() { return source(primaryHost, primaryPort, "identity_app", "local_identity", false); }
    @Bean("catalogDataSource")
    DataSource catalogDataSource() { return source(primaryHost, primaryPort, "catalog_app", "local_catalog", false); }
    @Bean("billingDataSource")
    DataSource billingDataSource() { return source(primaryHost, primaryPort, "billing_app", "local_billing", false); }
    @Bean("notificationDataSource")
    DataSource notificationDataSource() { return source(primaryHost, primaryPort, "notification_app", "local_notification", false); }
    @Bean("replicaDataSource")
    DataSource replicaDataSource() { return source(replicaHost, replicaPort, "replica_reader", "local_reader", true); }
    @Bean("bookingDataSource") @Primary
    DataSource bookingDataSource() { return source(primaryHost, primaryPort, "booking_app", "local_booking", false); }

    @Bean("identityJdbc")
    JdbcTemplate identityJdbc(@Qualifier("identityDataSource") DataSource ds) { return new JdbcTemplate(ds); }
    @Bean("catalogJdbc")
    JdbcTemplate catalogJdbc(@Qualifier("catalogDataSource") DataSource ds) { return new JdbcTemplate(ds); }
    @Bean("bookingJdbc")
    JdbcTemplate bookingJdbc(@Qualifier("bookingDataSource") DataSource ds) { return new JdbcTemplate(ds); }
    @Bean("billingJdbc")
    JdbcTemplate billingJdbc(@Qualifier("billingDataSource") DataSource ds) { return new JdbcTemplate(ds); }
    @Bean("notificationJdbc")
    JdbcTemplate notificationJdbc(@Qualifier("notificationDataSource") DataSource ds) { return new JdbcTemplate(ds); }
    @Bean("replicaJdbc")
    JdbcTemplate replicaJdbc(@Qualifier("replicaDataSource") DataSource ds) { return new JdbcTemplate(ds); }

    @Bean("bookingTransactionManager")
    DataSourceTransactionManager bookingTransactionManager(@Qualifier("bookingDataSource") DataSource ds) {
        return new DataSourceTransactionManager(ds);
    }
    @Bean("catalogTransactionManager")
    DataSourceTransactionManager catalogTransactionManager(@Qualifier("catalogDataSource") DataSource ds) {
        return new DataSourceTransactionManager(ds);
    }
}
