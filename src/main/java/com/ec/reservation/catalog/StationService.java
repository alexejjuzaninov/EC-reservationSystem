package com.ec.reservation.catalog;

import com.ec.reservation.identity.IdentityService;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.web.server.ResponseStatusException;
import static org.springframework.http.HttpStatus.*;

@Service
public class StationService {
    public record Station(UUID id, UUID ownerId, String ownerName, String ownerKind, String name,
                          String address, String city, String connector, int powerKw,
                          int pricePerHourCents, String accessNote, boolean active,
                          String countryCode, double latitude, double longitude, boolean synthetic,
                          String listingStatus, boolean requiresBookingApproval) {}
    public record NewStation(@NotBlank String name, @NotBlank String address, @NotBlank String city,
                             @NotBlank @Pattern(regexp = "Type 2|CCS2") String connector,
                             @Min(1) @Max(350) int powerKw,
                             @Min(0) @Max(1000000) int pricePerHourCents, String accessNote,
                             @NotBlank @Pattern(regexp = "CZ|US") String countryCode,
                             @NotNull @DecimalMin("-90.0") @DecimalMax("90.0") Double latitude,
                             @NotNull @DecimalMin("-180.0") @DecimalMax("180.0") Double longitude,
                             Boolean requiresBookingApproval) {}
    public record StationPage(List<Station> items, long total, int page, int size, int pages) {}

    static final String FIELDS = "s.*, ST_Y(s.location) AS latitude, ST_X(s.location) AS longitude";
    private final JdbcTemplate primary;
    private final JdbcTemplate replica;
    private final ClusterCache cache;

    StationService(@Qualifier("catalogJdbc") JdbcTemplate primary, @Qualifier("replicaJdbc") JdbcTemplate replica,
                   ClusterCache cache) {
        this.primary = primary; this.replica = replica; this.cache = cache;
    }

    static Station map(ResultSet rs, int row) throws SQLException {
        return new Station(rs.getObject("id", UUID.class), rs.getObject("owner_id", UUID.class),
            rs.getString("owner_name"), rs.getString("owner_kind"), rs.getString("name"),
            rs.getString("address"), rs.getString("city"), rs.getString("connector"),
            rs.getInt("power_kw"), rs.getInt("price_per_hour_cents"), rs.getString("access_note"),
            rs.getBoolean("active"), rs.getString("country_code"), rs.getDouble("latitude"),
            rs.getDouble("longitude"), rs.getBoolean("synthetic"), rs.getString("listing_status"),
            rs.getBoolean("requires_booking_approval"));
    }

    static Station asPublic(Station station) {
        return new Station(station.id(), station.ownerId(), station.ownerName(), station.ownerKind(),
            station.name(), station.address(), station.city(), station.connector(), station.powerKw(),
            station.pricePerHourCents(), "", station.active(), station.countryCode(), station.latitude(),
            station.longitude(), station.synthetic(), station.listingStatus(), station.requiresBookingApproval());
    }

    private void invalidateAfterCommit(String country) {
        if (TransactionSynchronizationManager.isSynchronizationActive()) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override public void afterCommit() { cache.invalidate(country); }
            });
        } else cache.invalidate(country);
    }

    public List<Station> list(String city, String connector, String country, boolean consistent) {
        String sql = "SELECT " + FIELDS + " FROM catalog.stations s WHERE s.active AND s.listing_status = 'APPROVED' "
            + "AND s.country_code = ? AND (? = '' OR s.city ILIKE ?) AND (? = '' OR s.connector = ?) "
            + "ORDER BY s.synthetic, s.created_at DESC, s.name LIMIT 24";
        String cityFilter = city == null ? "" : city.trim();
        String connectorFilter = connector == null ? "" : connector.trim();
        String countryFilter = country == null ? "CZ" : country;
        Object[] args = {countryFilter, cityFilter, "%" + cityFilter + "%", connectorFilter, connectorFilter};
        if (consistent) return primary.query(sql, StationService::map, args).stream().map(StationService::asPublic).toList();
        try { return replica.query(sql, StationService::map, args).stream().map(StationService::asPublic).toList(); }
        catch (DataAccessException error) { return primary.query(sql, StationService::map, args).stream().map(StationService::asPublic).toList(); }
    }

    public Station get(UUID id) {
        return primary.query("SELECT " + FIELDS + " FROM catalog.stations s WHERE s.id = ?", StationService::map, id)
            .stream().findFirst().orElseThrow(() -> new ResponseStatusException(NOT_FOUND, "Station not found"));
    }

    public Station publicStation(UUID id) {
        Station station = get(id);
        if (!station.active() || !station.listingStatus().equals("APPROVED"))
            throw new ResponseStatusException(NOT_FOUND, "Station is not published");
        return asPublic(station);
    }

    public List<Station> publicByIds(List<UUID> ids) {
        if (ids.isEmpty()) return List.of();
        if (ids.size() > 100) throw new ResponseStatusException(BAD_REQUEST, "Too many station IDs");
        String placeholders = String.join(",", Collections.nCopies(ids.size(), "?"));
        Map<UUID, Station> found = primary.query("SELECT " + FIELDS + " FROM catalog.stations s WHERE s.id IN (" + placeholders + ")",
            StationService::map, ids.toArray()).stream().map(StationService::asPublic)
            .collect(Collectors.toMap(Station::id, station -> station));
        return ids.stream().map(found::get).filter(java.util.Objects::nonNull).toList();
    }

    public List<Station> forOwner(IdentityService.User actor) {
        return primary.query("SELECT " + FIELDS + " FROM catalog.stations s WHERE s.owner_id = ? ORDER BY s.created_at DESC LIMIT 100",
            StationService::map, actor.id());
    }

    public List<Station> pending(IdentityService.User actor) {
        if (!actor.kind().equals("ADMIN")) throw new ResponseStatusException(FORBIDDEN, "Administrator access required");
        return primary.query("SELECT " + FIELDS + " FROM catalog.stations s WHERE s.listing_status = 'PENDING' ORDER BY s.created_at LIMIT 100",
            StationService::map);
    }

    public StationPage adminPage(IdentityService.User actor, String country, String status,
                                 String ownerKind, String query, int page, int size) {
        if (!actor.kind().equals("ADMIN")) throw new ResponseStatusException(FORBIDDEN, "Administrator access required");
        if (page < 0 || page > 10000 || size < 1 || size > 50)
            throw new ResponseStatusException(BAD_REQUEST, "Invalid page size or number");
        String countryFilter = country == null ? "" : country.trim();
        String statusFilter = status == null ? "" : status.trim();
        String ownerFilter = ownerKind == null ? "" : ownerKind.trim();
        String search = query == null ? "" : query.trim();
        if (!countryFilter.isEmpty() && !List.of("CZ", "US").contains(countryFilter)
            || !statusFilter.isEmpty() && !List.of("APPROVED", "PENDING", "REJECTED").contains(statusFilter)
            || !ownerFilter.isEmpty() && !List.of("PERSON", "COMPANY", "PLATFORM").contains(ownerFilter)
            || search.length() > 80)
            throw new ResponseStatusException(BAD_REQUEST, "Invalid station filters");
        StringBuilder where = new StringBuilder(" FROM catalog.stations s WHERE TRUE");
        List<Object> args = new ArrayList<>();
        if (!countryFilter.isEmpty()) { where.append(" AND s.country_code = ?"); args.add(countryFilter); }
        if (!statusFilter.isEmpty()) { where.append(" AND s.listing_status = ?"); args.add(statusFilter); }
        if (!ownerFilter.isEmpty()) { where.append(" AND s.owner_kind = ?"); args.add(ownerFilter); }
        if (!search.isEmpty()) {
            where.append(" AND (s.name ILIKE ? OR s.city ILIKE ? OR s.owner_name ILIKE ?)");
            String pattern = "%" + search + "%";
            args.add(pattern); args.add(pattern); args.add(pattern);
        }
        long total = primary.queryForObject("SELECT count(*)" + where, Long.class, args.toArray());
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(size); pageArgs.add((long) page * size);
        List<Station> items = primary.query("SELECT " + FIELDS + where
            + " ORDER BY s.synthetic, s.created_at DESC, s.id LIMIT ? OFFSET ?",
            StationService::map, pageArgs.toArray());
        return new StationPage(items, total, page, size, (int) ((total + size - 1) / size));
    }

    @Transactional("catalogTransactionManager")
    public Station create(IdentityService.User actor, NewStation input) {
        if (!List.of("PERSON", "COMPANY", "PLATFORM").contains(actor.kind()))
            throw new ResponseStatusException(FORBIDDEN, "Only hosts and companies can add stations");
        if (input.countryCode().equals("CZ") && (input.latitude() < 48.4 || input.latitude() > 51.1 || input.longitude() < 12.0 || input.longitude() > 19.0))
            throw new ResponseStatusException(BAD_REQUEST, "The location must be in Czechia");
        if (input.countryCode().equals("US") && (input.latitude() < 24.0 || input.latitude() > 50.0 || input.longitude() < -125.0 || input.longitude() > -66.0))
            throw new ResponseStatusException(BAD_REQUEST, "The US demo covers the contiguous states");
        UUID id = UUID.randomUUID();
        String status = actor.kind().equals("PLATFORM") ? "APPROVED" : "PENDING";
        primary.update("INSERT INTO catalog.stations (id, owner_id, owner_name, owner_kind, name, address, city, connector, power_kw, price_per_hour_cents, access_note, country_code, location, listing_status, requires_booking_approval) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ST_SetSRID(ST_MakePoint(?, ?), 4326), ?, ?)",
            id, actor.id(), actor.name(), actor.kind(), input.name().trim(), input.address().trim(), input.city().trim(),
            input.connector().trim(), input.powerKw(), input.pricePerHourCents(), input.accessNote() == null ? "" : input.accessNote().trim(),
            input.countryCode(), input.longitude(), input.latitude(), status, Boolean.TRUE.equals(input.requiresBookingApproval()));
        if (status.equals("PENDING")) primary.update("INSERT INTO catalog.outbox (id, station_id, owner_id, event_type) VALUES (?, ?, ?, 'STATION_SUBMITTED')", UUID.randomUUID(), id, actor.id());
        invalidateAfterCommit(input.countryCode());
        return get(id);
    }

    @Transactional("catalogTransactionManager")
    public Station setActive(UUID id, IdentityService.User actor, boolean active) {
        Station station = get(id);
        if (!station.ownerId().equals(actor.id()) && !actor.kind().equals("ADMIN"))
            throw new ResponseStatusException(FORBIDDEN, "This station belongs to another host");
        primary.update("UPDATE catalog.stations SET active = ? WHERE id = ?", active, id);
        invalidateAfterCommit(station.countryCode());
        return get(id);
    }

    @Transactional("catalogTransactionManager")
    public Station setBookingApproval(UUID id, IdentityService.User actor, boolean required) {
        Station station = get(id);
        if (!station.ownerId().equals(actor.id()))
            throw new ResponseStatusException(FORBIDDEN, "Only the station owner can change booking approval");
        primary.update("UPDATE catalog.stations SET requires_booking_approval = ? WHERE id = ?", required, id);
        return get(id);
    }

    @Transactional("catalogTransactionManager")
    public int setFleetActive(IdentityService.User actor, boolean active) {
        if (!List.of("COMPANY", "PLATFORM").contains(actor.kind()))
            throw new ResponseStatusException(FORBIDDEN, "Fleet controls are available to companies and the EC network");
        List<String> countries = primary.queryForList(
            "SELECT DISTINCT country_code FROM catalog.stations WHERE owner_id = ?", String.class, actor.id());
        int changed = primary.update("UPDATE catalog.stations SET active = ? WHERE owner_id = ?",
            active, actor.id());
        countries.forEach(this::invalidateAfterCommit);
        return changed;
    }

    @Transactional("catalogTransactionManager")
    public Station decide(UUID id, IdentityService.User actor, boolean approve) {
        if (!actor.kind().equals("ADMIN")) throw new ResponseStatusException(FORBIDDEN, "Administrator access required");
        Station station = get(id);
        if (!station.listingStatus().equals("PENDING")) throw new ResponseStatusException(CONFLICT, "This listing has already been reviewed");
        primary.update("UPDATE catalog.stations SET listing_status = ? WHERE id = ?", approve ? "APPROVED" : "REJECTED", id);
        primary.update("INSERT INTO catalog.outbox (id, station_id, owner_id, event_type) VALUES (?, ?, ?, ?)",
            UUID.randomUUID(), id, station.ownerId(), approve ? "STATION_APPROVED" : "STATION_REJECTED");
        invalidateAfterCommit(station.countryCode());
        return get(id);
    }

    public long totalCount() {
        return primary.queryForObject("SELECT count(*) FROM catalog.stations WHERE listing_status = 'APPROVED'", Long.class);
    }
    public long pendingCount() {
        return primary.queryForObject("SELECT count(*) FROM catalog.stations WHERE listing_status = 'PENDING'", Long.class);
    }
}
