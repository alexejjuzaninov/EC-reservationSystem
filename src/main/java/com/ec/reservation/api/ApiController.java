package com.ec.reservation.api;

import com.ec.reservation.billing.BillingPreview;
import com.ec.reservation.booking.BookingService;
import com.ec.reservation.catalog.ClusterCache;
import com.ec.reservation.catalog.MapService;
import com.ec.reservation.catalog.StationService;
import com.ec.reservation.dashboard.DashboardService;
import com.ec.reservation.identity.IdentityService;
import com.ec.reservation.identity.SavedStationService;
import com.ec.reservation.notification.NotificationService;
import jakarta.validation.Valid;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api")
public class ApiController {
    private static final String DEFAULT_ACTOR = "10000000-0000-0000-0000-000000000001";
    private final IdentityService identity;
    private final StationService stations;
    private final SavedStationService savedStations;
    private final BookingService bookings;
    private final BillingPreview billing;
    private final MapService map;
    private final ClusterCache cache;
    private final NotificationService notifications;
    private final DashboardService dashboards;
    private final JdbcTemplate primary;
    private final JdbcTemplate replica;
    @Value("${app.preview.read-only:false}") private boolean previewReadOnly;

    ApiController(IdentityService identity, StationService stations, SavedStationService savedStations,
                  BookingService bookings, BillingPreview billing,
                  MapService map, ClusterCache cache, NotificationService notifications, DashboardService dashboards,
                  @Qualifier("bookingJdbc") JdbcTemplate primary, @Qualifier("replicaJdbc") JdbcTemplate replica) {
        this.identity = identity; this.stations = stations; this.savedStations = savedStations;
        this.bookings = bookings; this.billing = billing;
        this.map = map; this.cache = cache; this.notifications = notifications; this.dashboards = dashboards;
        this.primary = primary; this.replica = replica;
    }

    private IdentityService.User actor(String id) { return identity.require(id); }

    @GetMapping("/users")
    List<IdentityService.User> users() { return identity.users(); }

    @PostMapping("/users") @ResponseStatus(HttpStatus.CREATED)
    IdentityService.User createUser(@Valid @RequestBody IdentityService.NewUser input) { return identity.create(input); }

    @GetMapping("/stations")
    List<StationService.Station> stations(@RequestParam(required = false) String city,
                                          @RequestParam(required = false) String connector,
                                          @RequestParam(defaultValue = "CZ") String country,
                                          @RequestParam(defaultValue = "false") boolean consistent) {
        return stations.list(city, connector, country, consistent);
    }

    @GetMapping("/map/explore")
    MapService.MapView explore(@RequestParam(defaultValue = "CZ") String country,
                               @RequestParam double west, @RequestParam double south,
                               @RequestParam double east, @RequestParam double north,
                               @RequestParam int zoom, @RequestParam(required = false) String city,
                               @RequestParam(required = false) String connector,
                               @RequestParam(defaultValue = "24") int limit,
                               @RequestParam(defaultValue = "false") boolean consistent) {
        return map.explore(country, west, south, east, north, zoom, city, connector, limit, consistent);
    }

    @GetMapping("/stations/{id}")
    StationService.Station station(@PathVariable UUID id) { return stations.publicStation(id); }

    @GetMapping("/saved-stations")
    List<StationService.Station> savedStations(@RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user) {
        return savedStations.forDriver(actor(user));
    }

    @PutMapping("/saved-stations/{id}") @ResponseStatus(HttpStatus.NO_CONTENT)
    void saveStation(@PathVariable UUID id,
                     @RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user) {
        savedStations.save(id, actor(user));
    }

    @DeleteMapping("/saved-stations/{id}") @ResponseStatus(HttpStatus.NO_CONTENT)
    void removeSavedStation(@PathVariable UUID id,
                            @RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user) {
        savedStations.remove(id, actor(user));
    }

    @GetMapping("/my-stations")
    List<StationService.Station> myStations(@RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user) {
        return stations.forOwner(actor(user));
    }

    @PatchMapping("/my-stations/status")
    Map<String, Integer> fleetStatus(@RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user,
                                     @RequestBody Map<String, Boolean> input) {
        return Map.of("updated", stations.setFleetActive(actor(user), Boolean.TRUE.equals(input.get("active"))));
    }

    @GetMapping("/stations/{id}/availability")
    BookingService.Availability availability(@PathVariable UUID id, @RequestParam Instant startAt, @RequestParam Instant endAt) {
        return bookings.availability(id, startAt, endAt);
    }

    @PostMapping("/stations/availability-batch")
    List<BookingService.StationAvailability> batchAvailability(@RequestBody BookingService.BatchRequest input) {
        return bookings.batchAvailability(input);
    }

    @GetMapping("/stations/{id}/weekly-hours")
    BookingService.WeeklySchedule weeklyHours(@PathVariable UUID id,
                                              @RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user) {
        return bookings.weekly(id, actor(user));
    }

    @PutMapping("/stations/{id}/weekly-hours")
    BookingService.WeeklySchedule setWeeklyHours(@PathVariable UUID id,
                                                 @RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user,
                                                 @RequestBody BookingService.NewWeeklySchedule input) {
        return bookings.setWeekly(id, actor(user), input);
    }

    @DeleteMapping("/stations/{id}/weekly-hours") @ResponseStatus(HttpStatus.NO_CONTENT)
    void resetWeeklyHours(@PathVariable UUID id,
                          @RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user) {
        bookings.resetWeekly(id, actor(user));
    }

    @GetMapping("/stations/{id}/blocks")
    List<BookingService.TimeBlock> stationBlocks(@PathVariable UUID id,
                                                 @RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user) {
        return bookings.blocks(id, actor(user));
    }

    @PostMapping("/stations/{id}/blocks") @ResponseStatus(HttpStatus.CREATED)
    BookingService.TimeBlock createStationBlock(@PathVariable UUID id,
                                                @RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user,
                                                @Valid @RequestBody BookingService.NewTimeBlock input) {
        return bookings.createBlock(id, actor(user), input);
    }

    @DeleteMapping("/stations/{id}/blocks/{blockId}") @ResponseStatus(HttpStatus.NO_CONTENT)
    void deleteStationBlock(@PathVariable UUID id, @PathVariable UUID blockId,
                            @RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user) {
        bookings.deleteBlock(id, blockId, actor(user));
    }

    @PostMapping("/stations") @ResponseStatus(HttpStatus.CREATED)
    StationService.Station createStation(@RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user,
                                         @Valid @RequestBody StationService.NewStation input) {
        return stations.create(actor(user), input);
    }

    @PatchMapping("/stations/{id}/status")
    StationService.Station stationStatus(@PathVariable UUID id,
                                        @RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user,
                                        @RequestBody Map<String, Boolean> input) {
        return stations.setActive(id, actor(user), Boolean.TRUE.equals(input.get("active")));
    }

    @GetMapping("/admin/stations/pending")
    List<StationService.Station> pendingStations(@RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user) {
        return stations.pending(actor(user));
    }

    @GetMapping("/admin/stations")
    StationService.StationPage adminStations(@RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user,
                                             @RequestParam(defaultValue = "") String country,
                                             @RequestParam(defaultValue = "") String status,
                                             @RequestParam(defaultValue = "") String ownerKind,
                                             @RequestParam(defaultValue = "") String query,
                                             @RequestParam(defaultValue = "0") int page,
                                             @RequestParam(defaultValue = "20") int size) {
        return stations.adminPage(actor(user), country, status, ownerKind, query, page, size);
    }

    @PostMapping("/admin/stations/{id}/decision")
    StationService.Station decideStation(@PathVariable UUID id,
                                         @RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user,
                                         @RequestBody Map<String, Boolean> input) {
        return stations.decide(id, actor(user), Boolean.TRUE.equals(input.get("approve")));
    }

    @GetMapping("/bookings")
    List<BookingService.Booking> bookings(@RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user) {
        return bookings.forActor(actor(user));
    }

    @GetMapping("/bookings/page")
    BookingService.BookingPage bookingPage(@RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user,
                                           @RequestParam(defaultValue = "") String status,
                                           @RequestParam(defaultValue = "") String country,
                                           @RequestParam(defaultValue = "0") int page,
                                           @RequestParam(defaultValue = "8") int size) {
        return bookings.pageForActor(actor(user), status, country, page, size);
    }

    @PostMapping("/bookings") @ResponseStatus(HttpStatus.CREATED)
    BookingService.Booking createBooking(@RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user,
                                         @Valid @RequestBody BookingService.NewBooking input) {
        return bookings.create(actor(user), input);
    }

    @PostMapping("/bookings/{id}/cancel")
    BookingService.Booking cancel(@PathVariable UUID id,
                                  @RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user) {
        return bookings.cancel(id, actor(user));
    }

    @GetMapping("/bookings/{id}/payment-preview")
    BillingPreview.Charge payment(@PathVariable UUID id,
                                  @RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user) {
        BookingService.Booking booking = bookings.get(id);
        IdentityService.User actor = actor(user);
        if (!booking.driverId().equals(actor.id()) && !booking.ownerId().equals(actor.id()) && !actor.kind().equals("ADMIN"))
            throw new org.springframework.web.server.ResponseStatusException(HttpStatus.FORBIDDEN, "You cannot view this payment");
        return billing.charge(id);
    }

    @GetMapping("/system")
    Map<String, Object> system() {
        boolean primaryOnline;
        boolean replicaOnline;
        try { primaryOnline = Integer.valueOf(1).equals(primary.queryForObject("SELECT 1", Integer.class)); }
        catch (Exception error) { primaryOnline = false; }
        try { replicaOnline = Boolean.TRUE.equals(replica.queryForObject("SELECT pg_is_in_recovery()", Boolean.class)); }
        catch (Exception error) { replicaOnline = false; }
        return Map.of("primary", primaryOnline ? "online" : "unavailable", "replica", replicaOnline ? "streaming" : "unavailable",
            "redis", cache.online() ? "online" : "unavailable", "payments", "simulated", "metrics", "simulated", "commissionPercent", 12,
            "readOnly", previewReadOnly);
    }

    @GetMapping("/dashboard")
    DashboardService.Dashboard dashboard(@RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user) {
        return dashboards.forActor(actor(user));
    }

    @GetMapping("/notifications")
    List<NotificationService.Message> notifications(@RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user) {
        return notifications.forUser(actor(user).id());
    }

    @PatchMapping("/notifications/{id}/read")
    Map<String, Boolean> readNotification(@PathVariable UUID id,
                                          @RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user) {
        notifications.markRead(id, actor(user).id());
        return Map.of("read", true);
    }

    @GetMapping("/stations/{id}/telemetry-preview")
    DashboardService.Telemetry telemetry(@PathVariable UUID id,
                                         @RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user) {
        return dashboards.telemetry(id, actor(user));
    }

    @GetMapping("/events/preview")
    Map<String, Object> events(@RequestHeader(value = "X-Demo-User", defaultValue = DEFAULT_ACTOR) String user) {
        return dashboards.events(actor(user));
    }

    @GetMapping("/metrics/preview")
    Map<String, Object> metrics() {
        Long sessions = primary.queryForObject("SELECT count(*) FROM reservation.bookings WHERE status = 'CONFIRMED' AND start_at >= now() - interval '30 days' AND start_at < now()", Long.class);
        Long revenue = primary.queryForObject("SELECT coalesce(sum(total_cents), 0) FROM reservation.bookings WHERE status = 'CONFIRMED' AND country_code = 'CZ' AND start_at >= now() - interval '30 days' AND start_at < now()", Long.class);
        long count = sessions == null ? 0 : sessions;
        return Map.of("simulated", true, "label", "Last 30 days · fictional reservations", "utilizationPercent", 31 + Math.floorMod(java.time.LocalDate.now().getDayOfYear(), 18),
            "energyKwh", count * 34, "sessions", count, "revenueCents", revenue == null ? 0 : revenue, "revenueCurrency", "CZK");
    }
}
