package com.ec.reservation;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.time.LocalDate;
import java.time.ZoneOffset;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

@Service
public class DashboardService {
    public record Metric(String label, long value, String format, boolean simulated, String countryCode) {}
    public record Dashboard(String role, String title, String subtitle, List<Metric> metrics, long unreadNotifications) {}
    public record Telemetry(boolean simulated, String state, int energyKwhToday, int utilizationPercent, int powerKw) {}
    private final StationService stations;
    private final BookingService bookings;
    private final NotificationService notifications;
    private final JdbcTemplate catalog;
    private final JdbcTemplate booking;

    DashboardService(StationService stations, BookingService bookings, NotificationService notifications,
                     @Qualifier("catalogJdbc") JdbcTemplate catalog, @Qualifier("bookingJdbc") JdbcTemplate booking) {
        this.stations = stations; this.bookings = bookings; this.notifications = notifications;
        this.catalog = catalog; this.booking = booking;
    }

    public Dashboard forActor(IdentityService.User actor) {
        long unread = notifications.unread(actor.id());
        if (actor.kind().equals("ADMIN")) return new Dashboard("ADMIN", "Control room", "Review listings and oversee the network",
            List.of(new Metric("Stations in catalog", stations.totalCount(), "count", false, null),
                    new Metric("Awaiting review", stations.pendingCount(), "count", false, null),
                    new Metric("Reservations", bookings.totalCount(), "count", false, null)), unread);
        if (actor.kind().equals("DRIVER")) {
            List<BookingService.Booking> own = bookings.forActor(actor);
            long active = own.stream().filter(b -> b.status().equals("CONFIRMED")).count();
            long spentCz = own.stream().filter(b -> b.status().equals("CONFIRMED") && b.countryCode().equals("CZ"))
                .mapToLong(BookingService.Booking::totalCents).sum();
            long spentUs = own.stream().filter(b -> b.status().equals("CONFIRMED") && b.countryCode().equals("US"))
                .mapToLong(BookingService.Booking::totalCents).sum();
            return new Dashboard("DRIVER", "Your charging journey", "Plan a stop and keep every reservation in view",
                List.of(new Metric("Active reservations", active, "count", false, null),
                        new Metric("All reservations", own.size(), "count", false, null),
                        new Metric("Estimated · Czechia", spentCz, "money", true, "CZ"),
                        new Metric("Estimated · United States", spentUs, "money", true, "US")), unread);
        }
        List<StationService.Station> ownStations = stations.forOwner(actor);
        List<BookingService.Booking> incoming = bookings.forActor(actor).stream()
            .filter(b -> b.ownerId().equals(actor.id())).toList();
        boolean platform = actor.kind().equals("PLATFORM");
        long payoutCz = incoming.stream().filter(b -> b.status().equals("CONFIRMED") && b.countryCode().equals("CZ"))
            .mapToLong(b -> platform ? b.totalCents() : b.totalCents() - b.platformFeeCents()).sum();
        long payoutUs = incoming.stream().filter(b -> b.status().equals("CONFIRMED") && b.countryCode().equals("US"))
            .mapToLong(b -> platform ? b.totalCents() : b.totalCents() - b.platformFeeCents()).sum();
        String title = switch (actor.kind()) {
            case "COMPANY" -> "Company fleet";
            case "PLATFORM" -> "EC network";
            default -> "Your home charger";
        };
        return new Dashboard(actor.kind(), title, "Manage availability and incoming reservations",
            List.of(new Metric("Your stations", ownStations.size(), "count", false, null),
                    new Metric("Incoming reservations", incoming.size(), "count", false, null),
                    new Metric(platform ? "Revenue · Czechia" : "Estimated payout · Czechia", payoutCz, "money", true, "CZ"),
                    new Metric(platform ? "Revenue · United States" : "Estimated payout · United States", payoutUs, "money", true, "US")), unread);
    }

    public Telemetry telemetry(UUID stationId, IdentityService.User actor) {
        StationService.Station station = stations.get(stationId);
        if (!station.ownerId().equals(actor.id()) && !actor.kind().equals("ADMIN"))
            throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.FORBIDDEN, "You cannot view this station's telemetry");
        int day = LocalDate.now(ZoneOffset.UTC).getDayOfYear();
        int seed = Math.floorMod(stationId.hashCode() ^ (day * 7919), 1000);
        int utilization = station.active() ? 18 + seed % 57 : 0;
        // One plug's daily energy is bounded by rated power and occupied hours.
        int energy = station.active() ? (int) Math.round(station.powerKw() * 24.0 * utilization / 100.0
            * (0.38 + (seed % 21) / 100.0)) : 0;
        return new Telemetry(true, !station.active() ? "OFFLINE" : seed % 4 == 0 ? "CHARGING" : "AVAILABLE",
            energy, utilization, station.powerKw());
    }

    public Map<String, Object> events(IdentityService.User actor) {
        if (!actor.kind().equals("ADMIN"))
            throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.FORBIDDEN, "Administrator access required");
        Long bookingPending = booking.queryForObject("SELECT count(*) FROM reservation.outbox WHERE billing_processed_at IS NULL OR notification_processed_at IS NULL", Long.class);
        Long catalogPending = catalog.queryForObject("SELECT count(*) FROM catalog.outbox WHERE notification_processed_at IS NULL", Long.class);
        return Map.of("simulated", true, "transport", "local outbox / mock Kafka", "topics", List.of("reservation.events", "catalog.events"),
            "pendingReservationEvents", bookingPending, "pendingCatalogEvents", catalogPending);
    }
}
