package com.ec.reservation.notification;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

@Service
public class NotificationService {
    public record Message(UUID id, String type, String title, String body, Instant createdAt, boolean read,
                          UUID bookingId, UUID stationId) {}
    private record BookingEvent(UUID eventId, UUID bookingId, String type) {}
    private record StationEvent(UUID eventId, UUID stationId, UUID ownerId, String type) {}
    private record BookingPart(UUID driverId, UUID ownerId, String stationName) {}
    private static final UUID ADMIN_ID = UUID.fromString("10000000-0000-0000-0000-000000000006");
    private final JdbcTemplate notification;
    private final JdbcTemplate booking;
    private final JdbcTemplate catalog;
    @Value("${app.preview.read-only:false}") private boolean previewReadOnly;

    NotificationService(@Qualifier("notificationJdbc") JdbcTemplate notification,
                        @Qualifier("bookingJdbc") JdbcTemplate booking,
                        @Qualifier("catalogJdbc") JdbcTemplate catalog) {
        this.notification = notification; this.booking = booking; this.catalog = catalog;
    }

    private Message map(ResultSet rs, int row) throws SQLException {
        return new Message(rs.getObject("id", UUID.class), rs.getString("type"), rs.getString("title"),
            rs.getString("body"), rs.getTimestamp("created_at").toInstant(), rs.getTimestamp("read_at") != null,
            rs.getObject("booking_id", UUID.class), rs.getObject("station_id", UUID.class));
    }

    public List<Message> forUser(UUID userId) {
        return notification.query("SELECT * FROM notification.messages WHERE user_id = ? ORDER BY created_at DESC LIMIT 50", this::map, userId);
    }
    public long unread(UUID userId) {
        return notification.queryForObject("SELECT count(*) FROM notification.messages WHERE user_id = ? AND read_at IS NULL", Long.class, userId);
    }
    public void markRead(UUID messageId, UUID userId) {
        notification.update("UPDATE notification.messages SET read_at = coalesce(read_at, now()) WHERE id = ? AND user_id = ?", messageId, userId);
    }

    private void send(UUID eventId, UUID userId, String type, String title, String body, UUID bookingId, UUID stationId) {
        notification.update("INSERT INTO notification.messages (id, event_id, user_id, type, title, body, booking_id, station_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (event_id, user_id) DO NOTHING",
            UUID.randomUUID(), eventId, userId, type, title, body, bookingId, stationId);
    }

    @Scheduled(fixedDelay = 1800)
    public void dispatch() {
        if (previewReadOnly) return;
        List<BookingEvent> bookings = booking.query("SELECT id, booking_id, event_type FROM reservation.outbox WHERE notification_processed_at IS NULL ORDER BY created_at, id LIMIT 30",
            (rs, row) -> new BookingEvent(rs.getObject(1, UUID.class), rs.getObject(2, UUID.class), rs.getString(3)));
        for (BookingEvent event : bookings) {
            BookingPart part = booking.query("SELECT driver_id, owner_id, station_name FROM reservation.bookings WHERE id = ?",
                (rs, row) -> new BookingPart(rs.getObject(1, UUID.class), rs.getObject(2, UUID.class), rs.getString(3)), event.bookingId()).getFirst();
            if (event.type().equals("BOOKED")) {
                send(event.eventId(), part.driverId(), "BOOKING", "Reservation confirmed", "Your slot at " + part.stationName() + " is reserved.", event.bookingId(), null);
                send(event.eventId(), part.ownerId(), "BOOKING", "New reservation", "A driver reserved a slot at " + part.stationName() + ".", event.bookingId(), null);
            } else {
                send(event.eventId(), part.driverId(), "BOOKING", "Reservation cancelled", "Your slot at " + part.stationName() + " was released.", event.bookingId(), null);
                send(event.eventId(), part.ownerId(), "BOOKING", "Reservation cancelled", "The slot at " + part.stationName() + " is available again.", event.bookingId(), null);
            }
            booking.update("UPDATE reservation.outbox SET notification_processed_at = now() WHERE id = ?", event.eventId());
        }

        List<StationEvent> stations = catalog.query("SELECT id, station_id, owner_id, event_type FROM catalog.outbox WHERE notification_processed_at IS NULL ORDER BY created_at, id LIMIT 30",
            (rs, row) -> new StationEvent(rs.getObject(1, UUID.class), rs.getObject(2, UUID.class), rs.getObject(3, UUID.class), rs.getString(4)));
        for (StationEvent event : stations) {
            if (event.type().equals("STATION_SUBMITTED")) {
                send(event.eventId(), ADMIN_ID, "MODERATION", "Listing awaiting review", "A host submitted a new station.", null, event.stationId());
                send(event.eventId(), event.ownerId(), "MODERATION", "Station submitted", "An administrator will review your listing before it goes live.", null, event.stationId());
            } else {
                boolean approved = event.type().equals("STATION_APPROVED");
                send(event.eventId(), event.ownerId(), "MODERATION", approved ? "Station is live" : "Listing declined",
                    approved ? "Drivers can now find your station on the map." : "Please review the listing details and contact EC.", null, event.stationId());
            }
            catalog.update("UPDATE catalog.outbox SET notification_processed_at = now() WHERE id = ?", event.eventId());
        }
    }
}
