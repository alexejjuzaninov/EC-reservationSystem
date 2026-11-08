package com.ec.reservation.identity;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import java.util.List;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import static org.springframework.http.HttpStatus.BAD_REQUEST;

@Service
public class IdentityService {
    public record User(UUID id, String name, String kind) {}
    public record NewUser(@NotBlank String name,
                          @NotBlank @Pattern(regexp = "DRIVER|PERSON|COMPANY", message = "Choose driver, private host, or company") String kind) {}
    private final JdbcTemplate jdbc;

    IdentityService(@Qualifier("identityJdbc") JdbcTemplate jdbc) { this.jdbc = jdbc; }

    public List<User> users() {
        return jdbc.query("SELECT id, name, kind FROM identity.users ORDER BY CASE kind WHEN 'DRIVER' THEN 0 WHEN 'PERSON' THEN 1 WHEN 'COMPANY' THEN 2 ELSE 3 END",
            (rs, row) -> new User(rs.getObject("id", UUID.class), rs.getString("name"), rs.getString("kind")));
    }

    public User require(String id) {
        UUID uuid;
        try { uuid = UUID.fromString(id); }
        catch (IllegalArgumentException error) { throw new ResponseStatusException(BAD_REQUEST, "Unknown demo user"); }
        return jdbc.query("SELECT id, name, kind FROM identity.users WHERE id = ?",
            (rs, row) -> new User(rs.getObject("id", UUID.class), rs.getString("name"), rs.getString("kind")), uuid)
            .stream().findFirst().orElseThrow(() -> new ResponseStatusException(BAD_REQUEST, "Unknown demo user"));
    }

    public User create(NewUser input) {
        UUID id = UUID.randomUUID();
        jdbc.update("INSERT INTO identity.users (id, name, kind) VALUES (?, ?, ?)", id, input.name().trim(), input.kind());
        return require(id.toString());
    }
}
