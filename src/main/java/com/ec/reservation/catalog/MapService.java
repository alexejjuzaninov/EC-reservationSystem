package com.ec.reservation.catalog;

import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import static org.springframework.http.HttpStatus.BAD_REQUEST;

@Service
public class MapService {
    public record Cluster(double latitude, double longitude, long count, UUID stationId, int minPriceCents) {}
    public record MapView(long total, List<Cluster> clusters, List<StationService.Station> stations,
                          int cachedTiles, int queriedTiles, boolean simulatedLocations) {}
    private static final TypeReference<List<Cluster>> CLUSTER_LIST = new TypeReference<>() {};
    private final JdbcTemplate primary;
    private final JdbcTemplate replica;
    private final ClusterCache cache;
    private final ObjectMapper json;

    MapService(@Qualifier("catalogJdbc") JdbcTemplate primary, @Qualifier("replicaJdbc") JdbcTemplate replica,
               ClusterCache cache, ObjectMapper json) {
        this.primary = primary; this.replica = replica; this.cache = cache; this.json = json;
    }

    private static int tileX(double lon, int zoom) {
        int max = 1 << zoom;
        return Math.max(0, Math.min(max - 1, (int) Math.floor((lon + 180.0) / 360.0 * max)));
    }
    private static int tileY(double lat, int zoom) {
        int max = 1 << zoom;
        double rad = Math.toRadians(Math.max(-85.0511, Math.min(85.0511, lat)));
        double y = (1.0 - Math.log(Math.tan(rad) + 1.0 / Math.cos(rad)) / Math.PI) / 2.0 * max;
        return Math.max(0, Math.min(max - 1, (int) Math.floor(y)));
    }
    private static double lonAt(int x, int zoom) { return x * 360.0 / (1 << zoom) - 180.0; }
    private static double latAt(int y, int zoom) {
        return Math.toDegrees(Math.atan(Math.sinh(Math.PI * (1.0 - 2.0 * y / (1 << zoom)))));
    }

    private Cluster cluster(ResultSet rs, int row) throws SQLException {
        String id = rs.getString("station_id");
        return new Cluster(rs.getDouble("latitude"), rs.getDouble("longitude"), rs.getLong("station_count"),
            id == null ? null : UUID.fromString(id), rs.getInt("min_price_cents"));
    }

    private List<Cluster> queryTile(JdbcTemplate jdbc, String country, int zoom, int x, int y, String city, String connector) {
        double west = lonAt(x, zoom), east = lonAt(x + 1, zoom);
        double north = latAt(y, zoom), south = latAt(y + 1, zoom);
        // A projected grid keeps cluster cells close to 88 screen pixels at every latitude.
        double cellSize = 40_075_016.68557849 * 88.0 / (256.0 * (1 << zoom));
        String sql = "SELECT avg(ST_Y(s.location)) AS latitude, avg(ST_X(s.location)) AS longitude, "
            + "count(*) AS station_count, CASE WHEN count(*) = 1 THEN min(s.id::text) ELSE NULL END AS station_id, "
            + "min(s.price_per_hour_cents) AS min_price_cents "
            + "FROM catalog.stations s WHERE s.active AND s.listing_status = 'APPROVED' AND s.country_code = ? "
            + "AND s.location && ST_MakeEnvelope(?, ?, ?, ?, 4326) "
            + "AND (? = '' OR s.city ILIKE ?) AND (? = '' OR s.connector = ?) "
            + "GROUP BY ST_SnapToGrid(ST_Transform(s.location, 3857), ?) ORDER BY station_count DESC LIMIT 150";
        return jdbc.query(sql, this::cluster, country, west, south, east, north,
            city, "%" + city + "%", connector, connector, cellSize);
    }

    private List<Cluster> tile(String country, int zoom, int x, int y, String city, String connector,
                               boolean consistent, String version, int[] stats) {
        if (consistent || version.equals("offline")) {
            stats[1]++;
            return queryTile(primary, country, zoom, x, y, city, connector);
        }
        String filter = Base64.getUrlEncoder().withoutPadding().encodeToString((city + "|" + connector).getBytes(StandardCharsets.UTF_8));
        String key = "ec:map:clusters:v3:" + version + ":" + country + ":z" + zoom + ":" + x + ":" + y + ":" + filter;
        String cached = cache.get(key);
        if (cached != null) {
            try { stats[0]++; return json.readValue(cached, CLUSTER_LIST); }
            catch (Exception ignored) { }
        }
        List<Cluster> clusters;
        try { clusters = queryTile(replica, country, zoom, x, y, city, connector); }
        catch (DataAccessException error) { clusters = queryTile(primary, country, zoom, x, y, city, connector); }
        stats[1]++;
        try { cache.put(key, json.writeValueAsString(clusters)); }
        catch (Exception ignored) { }
        return clusters;
    }

    public MapView explore(String country, double west, double south, double east, double north,
                           int zoom, String city, String connector, int limit, boolean consistent) {
        if (!List.of("CZ", "US").contains(country) || west < -180 || east > 180 || south < -85 || north > 85
            || west >= east || south >= north || zoom < 3 || zoom > 18 || limit < 1 || limit > 100)
            throw new ResponseStatusException(BAD_REQUEST, "Invalid map area");
        String cityFilter = city == null ? "" : city.trim();
        String plugFilter = connector == null ? "" : connector.trim();
        int minX = tileX(west, zoom), maxX = tileX(east, zoom);
        int minY = tileY(north, zoom), maxY = tileY(south, zoom);
        if ((maxX - minX + 1L) * (maxY - minY + 1L) > 80)
            throw new ResponseStatusException(BAD_REQUEST, "Zoom in to explore this area");
        String version = cache.version(country);
        List<Cluster> clusters = new ArrayList<>();
        int[] stats = new int[2];
        for (int x = minX; x <= maxX; x++) for (int y = minY; y <= maxY; y++)
            clusters.addAll(tile(country, zoom, x, y, cityFilter, plugFilter, consistent, version, stats));
        clusters = clusters.stream().filter(c -> c.longitude() >= west && c.longitude() <= east
            && c.latitude() >= south && c.latitude() <= north).toList();
        JdbcTemplate source = consistent ? primary : replica;
        long total;
        List<StationService.Station> stations;
        try {
            total = count(source, country, west, south, east, north, cityFilter, plugFilter);
            stations = stations(source, country, west, south, east, north, cityFilter, plugFilter, limit);
        } catch (DataAccessException error) {
            total = count(primary, country, west, south, east, north, cityFilter, plugFilter);
            stations = stations(primary, country, west, south, east, north, cityFilter, plugFilter, limit);
        }
        return new MapView(total, clusters, stations, stats[0], stats[1], true);
    }

    private long count(JdbcTemplate jdbc, String country, double west, double south, double east, double north,
                       String city, String connector) {
        return jdbc.queryForObject("SELECT count(*) FROM catalog.stations s WHERE s.active AND s.listing_status = 'APPROVED' "
            + "AND s.country_code = ? AND s.location && ST_MakeEnvelope(?, ?, ?, ?, 4326) "
            + "AND (? = '' OR s.city ILIKE ?) AND (? = '' OR s.connector = ?)", Long.class,
            country, west, south, east, north, city, "%" + city + "%", connector, connector);
    }

    private List<StationService.Station> stations(JdbcTemplate jdbc, String country, double west, double south,
                                                   double east, double north, String city, String connector, int limit) {
        double centerLon = (west + east) / 2.0, centerLat = (south + north) / 2.0;
        return jdbc.query("SELECT " + StationService.FIELDS + " FROM catalog.stations s "
            + "WHERE s.active AND s.listing_status = 'APPROVED' AND s.country_code = ? "
            + "AND s.location && ST_MakeEnvelope(?, ?, ?, ?, 4326) "
            + "AND (? = '' OR s.city ILIKE ?) AND (? = '' OR s.connector = ?) "
            + "ORDER BY s.synthetic, s.location <-> ST_SetSRID(ST_MakePoint(?, ?), 4326) LIMIT ?",
            StationService::map, country, west, south, east, north,
            city, "%" + city + "%", connector, connector, centerLon, centerLat, limit)
            .stream().map(StationService::asPublic).toList();
    }
}
