param([string]$BaseUrl = 'http://localhost:18080')
$ErrorActionPreference = 'Stop'
$driver = '10000000-0000-0000-0000-000000000001'
$owner = '10000000-0000-0000-0000-000000000002'
$other = '10000000-0000-0000-0000-000000000005'
$admin = '10000000-0000-0000-0000-000000000006'

function Assert($condition, $message) {
    if (-not $condition) { throw "FAIL: $message" }
}
function Request($method, $path, $actor, $body) {
    $headers = @{ 'X-Demo-User' = $actor }
    $args = @{ Method = $method; Uri = "$BaseUrl/api$path"; Headers = $headers; ContentType = 'application/json; charset=utf-8' }
    if ($null -ne $body) { $args.Body = [System.Text.Encoding]::UTF8.GetBytes(($body | ConvertTo-Json -Compress -Depth 6)) }
    $result = Invoke-RestMethod @args
    if ($result -is [array]) { $result | ForEach-Object { Write-Output $_ } }
    else { return $result }
}

$system = Request GET '/system' $driver $null
Assert ($system.replica -eq 'streaming') 'read replica must be in recovery mode'
Assert ($system.redis -eq 'online') 'Redis must be online'
$adminDashboard = Request GET '/dashboard' $admin $null
Assert ($adminDashboard.metrics[0].value -ge 141354) 'expanded Czech and US synthetic locations must exist'
$catalogPage = Request GET '/admin/stations?page=0&size=20' $admin $null
Assert ($catalogPage.total -ge 141354 -and $catalogPage.items.Count -eq 20 -and $catalogPage.pages -gt 1) 'admin catalog must be paginated'
$bookingPage = Request GET '/bookings/page?page=0&size=8' $driver $null
Assert ($bookingPage.total -ge 8 -and $bookingPage.items.Count -le 8) 'demo reservations must be paginated'
$chebMap = Request GET '/map/explore?country=CZ&west=12.30&south=50.03&east=12.45&north=50.13&zoom=12&city=Cheb' $driver $null
Assert ($chebMap.total -ge 400 -and $chebMap.clusters.Count -gt 0) 'new Czech town coverage must be searchable'
$createdUser = Request POST '/users' $driver @{ name = "Preview-$([guid]::NewGuid().ToString('N').Substring(0,8))"; kind = 'COMPANY' }
Assert ($createdUser.kind -eq 'COMPANY' -and $createdUser.id) 'local account registration'
$owner = $createdUser.id
$start = (Get-Date).Date.AddDays(1).AddHours(10).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$end = (Get-Date).Date.AddDays(1).AddHours(11).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$city = "SmokeCity$([guid]::NewGuid().ToString('N').Substring(0,8))"
$mapPath = "/map/explore?country=CZ&west=14.45&south=50.04&east=14.55&north=50.12&zoom=12&city=$city"
$before = Request GET $mapPath $driver $null
Assert ($before.total -eq 0) 'unlisted city must have no map result'
$station = Request POST '/stations' $owner @{
    name = "Smoke-$([guid]::NewGuid().ToString('N').Substring(0,8))"; address = 'Test 1'; city = $city;
    connector = 'Type 2'; powerKw = 11; pricePerHourCents = 12000; accessNote = 'Test gate';
    countryCode = 'CZ'; latitude = 50.08; longitude = 14.5
}
Assert ($station.ownerId -eq $owner) 'station owner should be saved'
Assert ($station.listingStatus -eq 'PENDING') 'partner station should await moderation'
$hidden = $false
try { Request GET "/stations/$($station.id)" $driver $null | Out-Null }
catch { $hidden = ([int]$_.Exception.Response.StatusCode -eq 404) }
Assert $hidden 'pending station must not be public'
$pending = @(Request GET '/admin/stations/pending' $admin $null)
Assert (@($pending | Where-Object { $_.id -eq $station.id }).Count -eq 1) 'admin should see moderation request'
$decision = Request POST "/admin/stations/$($station.id)/decision" $admin @{ approve = $true }
Assert ($decision.listingStatus -eq 'APPROVED') 'admin should publish the station'

$replicated = $false
for ($i = 0; $i -lt 10; $i++) {
    $listed = @(Request GET "/stations?city=$city" $driver $null)
    if (@($listed | Where-Object { $_.id -eq $station.id }).Count -eq 1) { $replicated = $true; break }
    Start-Sleep -Milliseconds 500
}
Assert $replicated 'new station must appear on read replica'
$publicStation = Request GET "/stations/$($station.id)" $driver $null
Assert ($publicStation.accessNote -eq '') 'entry instructions must stay private until booking'
$mapped = Request GET $mapPath $driver $null
Assert ($mapped.total -eq 1 -and $mapped.stations[0].id -eq $station.id) 'map search must find approved station after cache invalidation'
$mappedAgain = Request GET $mapPath $driver $null
Assert ($mappedAgain.cachedTiles -gt 0) 'cluster tiles should be served from Redis'

$availability = Request GET "/stations/$($station.id)/availability?startAt=$([uri]::EscapeDataString($start))&endAt=$([uri]::EscapeDataString($end))" $driver $null
Assert ($availability.available -and $availability.quoteCents -eq 12000 -and $availability.platformFeeCents -eq 1440) 'availability and 12% fee'
$booking = Request POST '/bookings' $driver @{ stationId = $station.id; startAt = $start; endAt = $end }
Assert ($booking.status -eq 'CONFIRMED') 'booking should confirm'
Assert ($booking.countryCode -eq 'CZ') 'booking must retain country for currency'
Assert ($booking.accessNote -eq 'Test gate') 'confirmed driver should receive entry instructions'

$ownerBookings = @(Request GET '/bookings' $owner $null)
Assert (@($ownerBookings | Where-Object { $_.id -eq $booking.id }).Count -eq 1) 'owner should see the booking'
$conflict = $false
try { Request POST '/bookings' $other @{ stationId = $station.id; startAt = $start; endAt = $end } | Out-Null }
catch { $conflict = ([int]$_.Exception.Response.StatusCode -eq 409) }
Assert $conflict 'overlapping booking must return 409'

$payment = $null
for ($i = 0; $i -lt 12; $i++) {
    $payment = Request GET "/bookings/$($booking.id)/payment-preview" $driver $null
    if ($payment.status -eq 'SIMULATED') { break }
    Start-Sleep -Milliseconds 500
}
Assert ($payment.status -eq 'SIMULATED' -and $payment.ownerPayoutCents -eq 10560) 'outbox should create simulated payment and payout'
$notified = $false
for ($i = 0; $i -lt 12; $i++) {
    $notices = @(Request GET '/notifications' $driver $null)
    if (@($notices | Where-Object { $_.bookingId -eq $booking.id }).Count -gt 0) { $notified = $true; break }
    Start-Sleep -Milliseconds 500
}
Assert $notified 'booking event should create driver notification'

$cancelled = Request POST "/bookings/$($booking.id)/cancel" $driver $null
Assert ($cancelled.status -eq 'CANCELLED') 'cancel should update booking'
$availableAgain = Request GET "/stations/$($station.id)/availability?startAt=$([uri]::EscapeDataString($start))&endAt=$([uri]::EscapeDataString($end))" $driver $null
Assert $availableAgain.available 'cancel should release interval'

$forbidden = $false
try { Request PATCH "/stations/$($station.id)/status" $other @{ active = $false } | Out-Null }
catch { $forbidden = ([int]$_.Exception.Response.StatusCode -eq 403) }
Assert $forbidden 'other owner must not control station'

$disabled = Request PATCH "/stations/$($station.id)/status" $owner @{ active = $false }
Assert (-not $disabled.active) 'owner should close station'
$owned = @(Request GET '/my-stations' $owner $null)
Assert (@($owned | Where-Object { $_.id -eq $station.id -and -not $_.active }).Count -eq 1) 'closed station should remain in owner view'
Request PATCH "/stations/$($station.id)/status" $owner @{ active = $true } | Out-Null
$fleetClosed = Request PATCH '/my-stations/status' $owner @{ active = $false }
Assert ($fleetClosed.updated -ge 1) 'company should bulk close its stations'
$fleetOpen = Request PATCH '/my-stations/status' $owner @{ active = $true }
Assert ($fleetOpen.updated -ge 1) 'company should bulk reopen its stations'
$privateDenied = $false
try { Request PATCH '/my-stations/status' '10000000-0000-0000-0000-000000000002' @{ active = $false } | Out-Null }
catch { $privateDenied = ([int]$_.Exception.Response.StatusCode -eq 403) }
Assert $privateDenied 'private owner must not bulk manage fleet'

$usMap = Request GET '/map/explore?country=US&west=-74.12&south=40.62&east=-73.90&north=40.82&zoom=11' $other $null
Assert ($usMap.total -gt 100 -and $usMap.stations.Count -gt 0) 'US map should include synthetic locations'
$usStation = $usMap.stations[0]
$usStart = (Get-Date).Date.AddDays(1).AddHours(12).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$usEnd = (Get-Date).Date.AddDays(1).AddHours(13).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$usBooking = Request POST '/bookings' $other @{ stationId = $usStation.id; startAt = $usStart; endAt = $usEnd }
Assert ($usBooking.countryCode -eq 'US') 'US booking should retain dollar currency country'
Request POST "/bookings/$($usBooking.id)/cancel" $other $null | Out-Null
Write-Output "PASS: PostGIS 141k CZ/US, Redis cluster cache, replica, registration, moderation, booking, two-driver overlap, notification, simulated payout, cancellation, permissions"
