package com.ec.reservation;

import java.util.List;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import static org.springframework.http.HttpStatus.CONFLICT;
import static org.springframework.http.HttpStatus.FORBIDDEN;

@Service
public class SavedStationService {
    private final JdbcTemplate identity;
    private final StationService stations;

    SavedStationService(@Qualifier("identityJdbc") JdbcTemplate identity, StationService stations) {
        this.identity = identity;
        this.stations = stations;
    }

    private void requireDriver(IdentityService.User actor) {
        if (!actor.kind().equals("DRIVER"))
            throw new ResponseStatusException(FORBIDDEN, "Only drivers can save charging stations");
    }

    public List<StationService.Station> forDriver(IdentityService.User actor) {
        requireDriver(actor);
        List<UUID> ids = identity.queryForList(
            "SELECT station_id FROM identity.saved_stations WHERE user_id = ? ORDER BY created_at DESC, station_id LIMIT 100",
            UUID.class, actor.id());
        return stations.publicByIds(ids);
    }

    public void save(UUID stationId, IdentityService.User actor) {
        requireDriver(actor);
        Boolean alreadySaved = identity.queryForObject(
            "SELECT EXISTS (SELECT 1 FROM identity.saved_stations WHERE user_id = ? AND station_id = ?)",
            Boolean.class, actor.id(), stationId);
        if (Boolean.TRUE.equals(alreadySaved)) return;
        stations.publicStation(stationId);
        Long count = identity.queryForObject(
            "SELECT count(*) FROM identity.saved_stations WHERE user_id = ?", Long.class, actor.id());
        if (count != null && count >= 100)
            throw new ResponseStatusException(CONFLICT, "Remove a saved station before adding another");
        identity.update("INSERT INTO identity.saved_stations (user_id, station_id) VALUES (?, ?) ON CONFLICT DO NOTHING",
            actor.id(), stationId);
    }

    public void remove(UUID stationId, IdentityService.User actor) {
        requireDriver(actor);
        identity.update("DELETE FROM identity.saved_stations WHERE user_id = ? AND station_id = ?", actor.id(), stationId);
    }
}
