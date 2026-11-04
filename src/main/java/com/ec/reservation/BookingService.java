package com.ec.reservation;

import jakarta.validation.constraints.NotNull;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import static org.springframework.http.HttpStatus.*;

@Service
public class BookingService {
    public record Booking(UUID id, UUID stationId, String stationName, UUID ownerId, String ownerKind,
                          UUID driverId, String driverName, Instant startAt, Instant endAt,
                          String status, int totalCents, int platformFeeCents,
                          String stationAddress, String stationCity, String accessNote, String countryCode,
                          Double stationLatitude, Double stationLongitude) {}
    public record NewBooking(@NotNull UUID stationId, @NotNull Instant startAt, @NotNull Instant endAt) {}
    public record Availability(boolean available, String reason, int quoteCents, int platformFeeCents) {}
    public record BookingPage(List<Booking> items, long total, long confirmed, long cancelled,
                              int page, int size, int pages) {}
    public record TimeBlock(UUID id, UUID stationId, UUID ownerId, Instant startAt, Instant endAt, String reason) {}
    public record NewTimeBlock(@NotNull Instant startAt, @NotNull Instant endAt, String reason) {}
    public record WeeklyDay(int dayOfWeek, boolean enabled, int opensMinute, int closesMinute) {}
    public record WeeklySchedule(String zoneId, boolean configured, List<WeeklyDay> days) {}
    public record NewWeeklySchedule(String zoneId, List<WeeklyDay> days) {}
    public record BatchRequest(List<UUID> stationIds, Instant startAt, Instant endAt) {}
    public record StationAvailability(UUID stationId, boolean available, String reason, int quoteCents, int platformFeeCents) {}

    private final JdbcTemplate jdbc;
    private final StationService stations;
    BookingService(@Qualifier("bookingJdbc") JdbcTemplate jdbc, StationService stations) {
        this.jdbc = jdbc; this.stations = stations;
    }

    private Booking map(ResultSet rs, int row) throws SQLException {
        return new Booking(rs.getObject("id", UUID.class), rs.getObject("station_id", UUID.class),
            rs.getString("station_name"), rs.getObject("owner_id", UUID.class), rs.getString("owner_kind"),
            rs.getObject("driver_id", UUID.class), rs.getString("driver_name"),
            rs.getTimestamp("start_at").toInstant(), rs.getTimestamp("end_at").toInstant(),
            rs.getString("status"), rs.getInt("total_cents"), rs.getInt("platform_fee_cents"),
            rs.getString("station_address"), rs.getString("station_city"), rs.getString("access_note"),
            rs.getString("country_code"), rs.getObject("station_latitude", Double.class),
            rs.getObject("station_longitude", Double.class));
    }

    private TimeBlock mapBlock(ResultSet rs, int row) throws SQLException {
        return new TimeBlock(rs.getObject("id", UUID.class), rs.getObject("station_id", UUID.class),
            rs.getObject("owner_id", UUID.class), rs.getTimestamp("start_at").toInstant(),
            rs.getTimestamp("end_at").toInstant(), rs.getString("reason"));
    }

    private StationService.Station manageableStation(UUID stationId, IdentityService.User actor) {
        StationService.Station station = stations.get(stationId);
        if (!station.ownerId().equals(actor.id()) && !actor.kind().equals("ADMIN"))
            throw new ResponseStatusException(FORBIDDEN, "You cannot manage this station's schedule");
        return station;
    }

    private void lockSchedule(UUID stationId) {
        jdbc.query("SELECT pg_advisory_xact_lock(hashtextextended(?::text, 0))", rs -> null, stationId.toString());
    }

    private String defaultZone(StationService.Station station) {
        if (station.countryCode().equals("CZ")) return "Europe/Prague";
        if (station.city().equalsIgnoreCase("Phoenix")) return "America/Phoenix";
        double lon = station.longitude();
        if (lon < -113) return "America/Los_Angeles";
        if (lon < -101) return "America/Denver";
        if (lon < -85) return "America/Chicago";
        return "America/New_York";
    }

    private WeeklySchedule weekly(UUID stationId, StationService.Station station) {
        List<Map<String, Object>> rows = jdbc.queryForList(
            "SELECT day_of_week, zone_id, enabled, opens_minute, closes_minute FROM reservation.weekly_station_hours WHERE station_id = ? ORDER BY day_of_week", stationId);
        if (rows.isEmpty()) return new WeeklySchedule(defaultZone(station), false,
            java.util.stream.IntStream.rangeClosed(1, 7).mapToObj(day -> new WeeklyDay(day, true, 0, 1440)).toList());
        return new WeeklySchedule((String) rows.get(0).get("zone_id"), true, rows.stream()
            .map(row -> new WeeklyDay(((Number) row.get("day_of_week")).intValue(),
                (Boolean) row.get("enabled"), ((Number) row.get("opens_minute")).intValue(),
                ((Number) row.get("closes_minute")).intValue())).toList());
    }

    public WeeklySchedule weekly(UUID stationId, IdentityService.User actor) {
        return weekly(stationId, manageableStation(stationId, actor));
    }

    @Transactional("bookingTransactionManager")
    public WeeklySchedule setWeekly(UUID stationId, IdentityService.User actor, NewWeeklySchedule input) {
        StationService.Station station = manageableStation(stationId, actor);
        if (input == null || input.days() == null || input.days().size() != 7 || input.zoneId() == null)
            throw new ResponseStatusException(BAD_REQUEST, "Provide all seven days and a time zone");
        ZoneId zone;
        try { zone = ZoneId.of(input.zoneId()); }
        catch (Exception error) { throw new ResponseStatusException(BAD_REQUEST, "Choose a valid time zone"); }
        List<String> allowedZones = station.countryCode().equals("CZ") ? List.of("Europe/Prague")
            : List.of("America/New_York", "America/Chicago", "America/Denver", "America/Phoenix",
                "America/Los_Angeles", "America/Anchorage", "Pacific/Honolulu");
        if (!allowedZones.contains(zone.getId()))
            throw new ResponseStatusException(BAD_REQUEST, "Choose a time zone for this station's country");
        Set<Integer> days = new HashSet<>();
        for (WeeklyDay day : input.days()) {
            if (day == null || day.dayOfWeek() < 1 || day.dayOfWeek() > 7 || !days.add(day.dayOfWeek())
                || day.opensMinute() < 0 || day.opensMinute() >= day.closesMinute() || day.closesMinute() > 1440)
                throw new ResponseStatusException(BAD_REQUEST, "Each day needs one valid opening interval");
        }
        lockSchedule(stationId);
        jdbc.update("DELETE FROM reservation.weekly_station_hours WHERE station_id = ?", stationId);
        for (WeeklyDay day : input.days()) jdbc.update(
            "INSERT INTO reservation.weekly_station_hours (station_id, owner_id, day_of_week, zone_id, enabled, opens_minute, closes_minute) VALUES (?, ?, ?, ?, ?, ?, ?)",
            stationId, station.ownerId(), day.dayOfWeek(), zone.getId(), day.enabled(), day.opensMinute(), day.closesMinute());
        return weekly(stationId, station);
    }

    @Transactional("bookingTransactionManager")
    public void resetWeekly(UUID stationId, IdentityService.User actor) {
        manageableStation(stationId, actor);
        lockSchedule(stationId);
        jdbc.update("DELETE FROM reservation.weekly_station_hours WHERE station_id = ?", stationId);
    }

    private boolean withinWeekly(WeeklySchedule schedule, Instant start, Instant end) {
        if (!schedule.configured()) return true;
        ZoneId zone = ZoneId.of(schedule.zoneId());
        ZonedDateTime cursor = start.atZone(zone);
        while (cursor.toInstant().isBefore(end)) {
            LocalDate date = cursor.toLocalDate();
            WeeklyDay day = schedule.days().get(date.getDayOfWeek().getValue() - 1);
            Instant nextMidnight = date.plusDays(1).atStartOfDay(zone).toInstant();
            Instant segmentEnd = end.isBefore(nextMidnight) ? end : nextMidnight;
            int from = cursor.getHour() * 60 + cursor.getMinute();
            ZonedDateTime localEnd = segmentEnd.atZone(zone);
            int to = segmentEnd.equals(nextMidnight) ? 1440 : localEnd.getHour() * 60 + localEnd.getMinute();
            if (!day.enabled() || from < day.opensMinute() || to > day.closesMinute()) return false;
            cursor = segmentEnd.atZone(zone);
        }
        return true;
    }

    public List<TimeBlock> blocks(UUID stationId, IdentityService.User actor) {
        manageableStation(stationId, actor);
        return jdbc.query("SELECT * FROM reservation.station_time_blocks WHERE station_id = ? AND end_at > now() ORDER BY start_at LIMIT 200",
            this::mapBlock, stationId);
    }

    @Transactional("bookingTransactionManager")
    public TimeBlock createBlock(UUID stationId, IdentityService.User actor, NewTimeBlock input) {
        StationService.Station station = manageableStation(stationId, actor);
        if (input.startAt() == null || input.endAt() == null || !input.startAt().isAfter(Instant.now())
            || !input.endAt().isAfter(input.startAt()) || input.endAt().isAfter(input.startAt().plus(Duration.ofDays(14))))
            throw new ResponseStatusException(BAD_REQUEST, "Choose a future block lasting no more than 14 days");
        String reason = input.reason() == null ? "" : input.reason().trim();
        if (reason.length() > 100) throw new ResponseStatusException(BAD_REQUEST, "Keep the reason under 100 characters");
        lockSchedule(stationId);
        Integer bookings = jdbc.queryForObject(
            "SELECT count(*) FROM reservation.bookings WHERE station_id = ? AND status = 'CONFIRMED' AND start_at < ? AND end_at > ?",
            Integer.class, stationId, Timestamp.from(input.endAt()), Timestamp.from(input.startAt()));
        if (bookings != null && bookings > 0)
            throw new ResponseStatusException(CONFLICT, "A confirmed reservation already occupies this time");
        Integer existing = jdbc.queryForObject(
            "SELECT count(*) FROM reservation.station_time_blocks WHERE station_id = ? AND start_at < ? AND end_at > ?",
            Integer.class, stationId, Timestamp.from(input.endAt()), Timestamp.from(input.startAt()));
        if (existing != null && existing > 0)
            throw new ResponseStatusException(CONFLICT, "This time already has a schedule block");
        UUID id = UUID.randomUUID();
        jdbc.update("INSERT INTO reservation.station_time_blocks (id, station_id, owner_id, start_at, end_at, reason) VALUES (?, ?, ?, ?, ?, ?)",
            id, stationId, station.ownerId(), Timestamp.from(input.startAt()), Timestamp.from(input.endAt()), reason);
        return new TimeBlock(id, stationId, station.ownerId(), input.startAt(), input.endAt(), reason);
    }

    @Transactional("bookingTransactionManager")
    public void deleteBlock(UUID stationId, UUID blockId, IdentityService.User actor) {
        manageableStation(stationId, actor);
        jdbc.update("DELETE FROM reservation.station_time_blocks WHERE id = ? AND station_id = ?", blockId, stationId);
    }

    private long validMinutes(Instant start, Instant end) {
        if (start == null || end == null || !start.isAfter(Instant.now()))
            throw new ResponseStatusException(BAD_REQUEST, "Start time must be in the future");
        long minutes = Duration.between(start, end).toMinutes();
        if (minutes < 30 || minutes > 240 || !end.equals(start.plus(Duration.ofMinutes(minutes))))
            throw new ResponseStatusException(BAD_REQUEST, "Choose a slot between 30 minutes and 4 hours");
        return minutes;
    }

    public Availability availability(UUID stationId, Instant start, Instant end) {
        StationService.Station station = stations.get(stationId);
        long minutes = validMinutes(start, end);
        int quote = (int) Math.round(station.pricePerHourCents() * minutes / 60.0);
        int fee = station.ownerKind().equals("PLATFORM") ? quote : (int) Math.round(quote * 0.12);
        if (!station.active() || !station.listingStatus().equals("APPROVED"))
            return new Availability(false, "This station is not available", quote, fee);
        if (!withinWeekly(weekly(stationId, station), start, end))
            return new Availability(false, "Outside this station's weekly hours", quote, fee);
        Integer blocks = jdbc.queryForObject(
            "SELECT count(*) FROM reservation.station_time_blocks WHERE station_id = ? AND start_at < ? AND end_at > ?",
            Integer.class, stationId, Timestamp.from(end), Timestamp.from(start));
        if (blocks != null && blocks > 0)
            return new Availability(false, "Unavailable during a host's blocked time", quote, fee);
        Integer conflicts = jdbc.queryForObject(
            "SELECT count(*) FROM reservation.bookings WHERE station_id = ? AND status = 'CONFIRMED' AND start_at < ? AND end_at > ?",
            Integer.class, stationId, Timestamp.from(end), Timestamp.from(start));
        return new Availability(conflicts == 0, conflicts == 0 ? "Available" : "This time is already booked", quote, fee);
    }

    public List<StationAvailability> batchAvailability(BatchRequest input) {
        if (input == null || input.stationIds() == null || input.stationIds().isEmpty()
            || input.stationIds().size() > 100 || input.stationIds().contains(null))
            throw new ResponseStatusException(BAD_REQUEST, "Choose between 1 and 100 stations");
        long minutes = validMinutes(input.startAt(), input.endAt());
        List<UUID> ids = input.stationIds().stream().distinct().toList();
        Map<UUID, StationService.Station> stationMap = new HashMap<>();
        for (StationService.Station station : stations.publicByIds(ids)) stationMap.put(station.id(), station);
        String marks = String.join(",", java.util.Collections.nCopies(ids.size(), "?"));
        Object[] idArgs = ids.toArray();
        Map<UUID, List<WeeklyDay>> dayMap = new HashMap<>();
        Map<UUID, String> zoneMap = new HashMap<>();
        jdbc.query("SELECT station_id, day_of_week, zone_id, enabled, opens_minute, closes_minute FROM reservation.weekly_station_hours WHERE station_id IN (" + marks + ") ORDER BY day_of_week",
            rs -> { UUID id = rs.getObject("station_id", UUID.class);
                dayMap.computeIfAbsent(id, ignored -> new ArrayList<>()).add(new WeeklyDay(rs.getInt("day_of_week"), rs.getBoolean("enabled"), rs.getInt("opens_minute"), rs.getInt("closes_minute")));
                zoneMap.put(id, rs.getString("zone_id")); }, idArgs);
        Set<UUID> blocked = overlappingIds("reservation.station_time_blocks", ids, input.startAt(), input.endAt(), false);
        Set<UUID> booked = overlappingIds("reservation.bookings", ids, input.startAt(), input.endAt(), true);
        List<StationAvailability> results = new ArrayList<>();
        for (UUID id : ids) {
            StationService.Station station = stationMap.get(id);
            if (station == null) continue;
            int quote = (int) Math.round(station.pricePerHourCents() * minutes / 60.0);
            int fee = station.ownerKind().equals("PLATFORM") ? quote : (int) Math.round(quote * 0.12);
            List<WeeklyDay> days = dayMap.get(id);
            boolean weeklyOpen = days == null || withinWeekly(new WeeklySchedule(zoneMap.get(id), true, days), input.startAt(), input.endAt());
            String reason = !station.active() || !station.listingStatus().equals("APPROVED") ? "This station is not available"
                : !weeklyOpen ? "Outside this station's weekly hours"
                : blocked.contains(id) ? "Unavailable during a host's blocked time"
                : booked.contains(id) ? "This time is already booked" : "Available";
            results.add(new StationAvailability(id, reason.equals("Available"), reason, quote, fee));
        }
        return results;
    }

    private Set<UUID> overlappingIds(String table, List<UUID> ids, Instant start, Instant end, boolean booking) {
        String marks = String.join(",", java.util.Collections.nCopies(ids.size(), "?"));
        List<Object> args = new ArrayList<>(ids);
        args.add(Timestamp.from(end)); args.add(Timestamp.from(start));
        return new HashSet<>(jdbc.query("SELECT DISTINCT station_id FROM " + table + " WHERE station_id IN (" + marks
            + ") AND start_at < ? AND end_at > ?" + (booking ? " AND status = 'CONFIRMED'" : ""),
            (rs, row) -> rs.getObject(1, UUID.class), args.toArray()));
    }

    @Transactional("bookingTransactionManager")
    public Booking create(IdentityService.User actor, NewBooking input) {
        if (!actor.kind().equals("DRIVER"))
            throw new ResponseStatusException(FORBIDDEN, "Only drivers can book charging slots");
        StationService.Station station = stations.get(input.stationId());
        if (!station.active() || !station.listingStatus().equals("APPROVED"))
            throw new ResponseStatusException(CONFLICT, "This station cannot be booked");
        if (station.ownerId().equals(actor.id()))
            throw new ResponseStatusException(BAD_REQUEST, "You do not need to book your own station");
        lockSchedule(input.stationId());
        Availability quote = availability(input.stationId(), input.startAt(), input.endAt());
        if (!quote.available()) throw new ResponseStatusException(CONFLICT, quote.reason());
        UUID id = UUID.randomUUID();
        try {
            jdbc.update("INSERT INTO reservation.bookings (id, station_id, station_name, owner_id, owner_kind, driver_id, driver_name, start_at, end_at, status, total_cents, platform_fee_cents, station_address, station_city, access_note, country_code, station_latitude, station_longitude) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'CONFIRMED', ?, ?, ?, ?, ?, ?, ?, ?)",
                id, station.id(), station.name(), station.ownerId(), station.ownerKind(), actor.id(), actor.name(),
                Timestamp.from(input.startAt()), Timestamp.from(input.endAt()), quote.quoteCents(), quote.platformFeeCents(),
                station.address(), station.city(), station.accessNote(), station.countryCode(),
                station.latitude(), station.longitude());
        } catch (DataIntegrityViolationException error) {
            throw new ResponseStatusException(CONFLICT, "Someone just booked this slot. Choose another time");
        }
        jdbc.update("INSERT INTO reservation.outbox (id, booking_id, event_type, total_cents, platform_fee_cents) VALUES (?, ?, 'BOOKED', ?, ?)",
            UUID.randomUUID(), id, quote.quoteCents(), quote.platformFeeCents());
        return get(id);
    }

    public Booking get(UUID id) {
        return jdbc.query("SELECT * FROM reservation.bookings WHERE id = ?", this::map, id)
            .stream().findFirst().orElseThrow(() -> new ResponseStatusException(NOT_FOUND, "Reservation not found"));
    }

    public List<Booking> forActor(IdentityService.User actor) {
        if (actor.kind().equals("ADMIN"))
            return jdbc.query("SELECT * FROM reservation.bookings ORDER BY created_at DESC LIMIT 100", this::map);
        return jdbc.query("SELECT * FROM reservation.bookings WHERE driver_id = ? OR owner_id = ? ORDER BY start_at DESC",
            this::map, actor.id(), actor.id());
    }

    public BookingPage pageForActor(IdentityService.User actor, String status, String country, int page, int size) {
        if (page < 0 || page > 10000 || size < 1 || size > 50)
            throw new ResponseStatusException(BAD_REQUEST, "Invalid reservation page");
        String statusFilter = status == null ? "" : status.trim();
        String countryFilter = country == null ? "" : country.trim();
        if (!statusFilter.isEmpty() && !List.of("CONFIRMED", "CANCELLED").contains(statusFilter)
            || !countryFilter.isEmpty() && !List.of("CZ", "US").contains(countryFilter))
            throw new ResponseStatusException(BAD_REQUEST, "Invalid reservation filters");
        StringBuilder where = new StringBuilder(" WHERE TRUE");
        List<Object> args = new ArrayList<>();
        if (!actor.kind().equals("ADMIN")) {
            where.append(" AND (driver_id = ? OR owner_id = ?)");
            args.add(actor.id()); args.add(actor.id());
        }
        if (!countryFilter.isEmpty()) { where.append(" AND country_code = ?"); args.add(countryFilter); }
        long[] counts = jdbc.queryForObject("SELECT count(*) FILTER (WHERE status = 'CONFIRMED'), "
                + "count(*) FILTER (WHERE status = 'CANCELLED') FROM reservation.bookings" + where,
            (rs, row) -> new long[]{rs.getLong(1), rs.getLong(2)}, args.toArray());
        if (!statusFilter.isEmpty()) { where.append(" AND status = ?"); args.add(statusFilter); }
        long total = statusFilter.equals("CONFIRMED") ? counts[0]
            : statusFilter.equals("CANCELLED") ? counts[1] : counts[0] + counts[1];
        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(size); pageArgs.add((long) page * size);
        String order = actor.kind().equals("ADMIN") ? " ORDER BY start_at DESC, id"
            : " ORDER BY CASE WHEN status = 'CONFIRMED' AND start_at >= now() THEN 0 ELSE 1 END, "
                + "CASE WHEN status = 'CONFIRMED' AND start_at >= now() THEN start_at END, start_at DESC, id";
        List<Booking> items = jdbc.query("SELECT * FROM reservation.bookings" + where
            + order + " LIMIT ? OFFSET ?", this::map, pageArgs.toArray());
        return new BookingPage(items, total, counts[0], counts[1], page, size, (int) ((total + size - 1) / size));
    }

    public long totalCount() {
        return jdbc.queryForObject("SELECT count(*) FROM reservation.bookings", Long.class);
    }

    @Transactional("bookingTransactionManager")
    public Booking cancel(UUID id, IdentityService.User actor) {
        Booking booking = jdbc.query("SELECT * FROM reservation.bookings WHERE id = ? FOR UPDATE", this::map, id)
            .stream().findFirst().orElseThrow(() -> new ResponseStatusException(NOT_FOUND, "Reservation not found"));
        if (!booking.driverId().equals(actor.id()) && !booking.ownerId().equals(actor.id()) && !actor.kind().equals("ADMIN"))
            throw new ResponseStatusException(FORBIDDEN, "You cannot manage this reservation");
        if (booking.status().equals("CANCELLED")) return booking;
        if (!booking.startAt().isAfter(Instant.now()))
            throw new ResponseStatusException(CONFLICT, "A reservation cannot be cancelled after it starts");
        jdbc.update("UPDATE reservation.bookings SET status = 'CANCELLED' WHERE id = ?", id);
        jdbc.update("INSERT INTO reservation.outbox (id, booking_id, event_type, total_cents, platform_fee_cents) VALUES (?, ?, 'CANCELLED', ?, ?)",
            UUID.randomUUID(), id, booking.totalCents(), booking.platformFeeCents());
        return get(id);
    }
}
