package com.ec.reservation.billing;

import java.util.List;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

@Service
public class BillingPreview {
    public record Charge(String status, int totalCents, int platformFeeCents, int ownerPayoutCents, boolean simulated) {}
    private record Event(UUID id, UUID bookingId, String type, int total, int fee) {}
    private final JdbcTemplate billing;
    private final JdbcTemplate booking;
    @Value("${app.preview.read-only:false}") private boolean previewReadOnly;

    BillingPreview(@Qualifier("billingJdbc") JdbcTemplate billing, @Qualifier("bookingJdbc") JdbcTemplate booking) {
        this.billing = billing; this.booking = booking;
    }

    public Charge charge(UUID bookingId) {
        return billing.query("SELECT status, total_cents, platform_fee_cents, owner_payout_cents FROM billing.simulated_charges WHERE booking_id = ?",
            (rs, row) -> new Charge(rs.getString(1), rs.getInt(2), rs.getInt(3), rs.getInt(4), true), bookingId)
            .stream().findFirst().orElse(new Charge("PENDING", 0, 0, 0, true));
    }

    @Scheduled(fixedDelay = 2000)
    public void dispatch() {
        if (previewReadOnly) return;
        List<Event> events = booking.query("SELECT id, booking_id, event_type, total_cents, platform_fee_cents FROM reservation.outbox WHERE billing_processed_at IS NULL ORDER BY created_at, id LIMIT 30",
            (rs, row) -> new Event(rs.getObject(1, UUID.class), rs.getObject(2, UUID.class), rs.getString(3), rs.getInt(4), rs.getInt(5)));
        for (Event event : events) {
            if (event.type().equals("BOOKED")) {
                billing.update("INSERT INTO billing.simulated_charges (booking_id, total_cents, platform_fee_cents, owner_payout_cents, status) VALUES (?, ?, ?, ?, 'SIMULATED') ON CONFLICT (booking_id) DO NOTHING",
                    event.bookingId(), event.total(), event.fee(), event.total() - event.fee());
            } else {
                billing.update("INSERT INTO billing.simulated_charges (booking_id, total_cents, platform_fee_cents, owner_payout_cents, status) VALUES (?, ?, ?, 0, 'CANCELLED') ON CONFLICT (booking_id) DO UPDATE SET status = 'CANCELLED', owner_payout_cents = 0",
                    event.bookingId(), event.total(), event.fee());
            }
            booking.update("UPDATE reservation.outbox SET billing_processed_at = now() WHERE id = ?", event.id());
        }
    }
}
