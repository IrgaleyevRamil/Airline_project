from flask import (

    Flask,

    render_template,

    request,

    redirect,

    url_for,

    jsonify,

    flash,

    session,

    abort

)

import psycopg

import uuid

import os

import secrets

import hmac
import re

from datetime import date, datetime



from db import get_connection
from destination_info import DESTINATION_INFO


import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from functools import lru_cache
from flask import Response






app = Flask(__name__)


# Presentation coordinates for the interactive flight globe.
# Flight, route and airport records still come from PostgreSQL; this map only
# supplies geographic coordinates for the airport codes used by the demo data.
AIRPORT_GLOBE_COORDINATES = {
    "ALA": (43.3521, 77.0405), "NQZ": (51.0222, 71.4669),
    "DXB": (25.2532, 55.3657), "IST": (41.2753, 28.7519),
    "LHR": (51.4700, -0.4543), "CDG": (49.0097, 2.5479),
    "FRA": (50.0379, 8.5622), "AMS": (52.3105, 4.7683),
    "FCO": (41.8003, 12.2389), "JFK": (40.6413, -73.7781),
    "LAX": (33.9416, -118.4085), "ORD": (41.9742, -87.9073),
    "DOH": (25.2731, 51.6081), "AUH": (24.4330, 54.6511),
    "SIN": (1.3644, 103.9915), "HKG": (22.3080, 113.9185),
    "ICN": (37.4602, 126.4407), "HND": (35.5494, 139.7798),
    "TAS": (41.2579, 69.2812), "FRU": (43.0613, 74.4776),
    "GYD": (40.4675, 50.0467), "TBS": (41.6692, 44.9547),
    "SVO": (55.9726, 37.4146), "PEK": (40.0799, 116.6031),
    "DEL": (28.5562, 77.1000), "KUL": (2.7456, 101.7099),
    "BKK": (13.6900, 100.7501), "SYD": (-33.9399, 151.1753),
    "MEL": (-37.6690, 144.8410), "YYZ": (43.6777, -79.6248),
    "YVR": (49.1967, -123.1815), "MEX": (19.4361, -99.0719),
    "GRU": (-23.4356, -46.4731), "EZE": (-34.8222, -58.5358),
    "MAD": (40.4983, -3.5676), "BCN": (41.2974, 2.0833),
    "ZRH": (47.4581, 8.5555), "VIE": (48.1103, 16.5697),
    "MUC": (48.3538, 11.7861), "CPH": (55.6180, 12.6508),
    "OSL": (60.1939, 11.1004), "ARN": (59.6519, 17.9186),
    "HEL": (60.3172, 24.9633), "WAW": (52.1657, 20.9671),
    "PRG": (50.1008, 14.2600), "BUD": (47.4298, 19.2611),
    "CAI": (30.1219, 31.4056), "JNB": (-26.1337, 28.2420),
    "NBO": (-1.3192, 36.9278), "ADD": (8.9779, 38.7993),
}

# Fixed password for the local admin panel.
ADMIN_PASSWORD = "1234"



# Set FLASK_SECRET_KEY to a stable random value before deployment.

app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)

app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")





def csrf_token():

    if "csrf_token" not in session:

        session["csrf_token"] = secrets.token_urlsafe(32)

    return session["csrf_token"]





app.jinja_env.globals["csrf_token"] = csrf_token





def check_csrf():

    if not hmac.compare_digest(request.form.get("csrf_token", ""),

                               session.get("csrf_token", "-")):

        abort(400)





@app.before_request
def protect_admin():
    if request.path.startswith("/admin/") or request.path == "/admin":
        if request.endpoint == "admin_login":
            return
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        check_csrf()
        password = request.form.get("password", "")

        if hmac.compare_digest(password, ADMIN_PASSWORD):
            session.clear()
            session["is_admin"] = True
            return redirect(url_for("dashboard"))

        error = "Неверный пароль."

    return render_template("admin_login.html", error=error)


@app.post("/admin/logout")

def admin_logout():

    check_csrf()

    session.clear()

    return redirect(url_for("home"))





# =========================================================

# DASHBOARD

# =========================================================



@app.route("/admin")
def dashboard():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    (SELECT COUNT(*) FROM flight) AS flights,
                    (SELECT COUNT(*) FROM passenger) AS passengers,
                    (SELECT COUNT(*) FROM booking) AS bookings,
                    (SELECT COUNT(*) FROM ticket) AS tickets,
                    (SELECT COUNT(*) FROM payment) AS payments,
                    (SELECT COUNT(*) FROM booking WHERE status = 'Confirmed') AS confirmed_bookings,
                    (
                        SELECT COUNT(*)
                        FROM flight
                        WHERE departure_time > CURRENT_TIMESTAMP
                          AND status IN ('Scheduled', 'Boarding')
                    ) AS upcoming_flights,
                    COALESCE(
                        (
                            SELECT SUM(t.price)
                            FROM ticket t
                            JOIN booking b ON b.booking_id = t.booking_id
                            WHERE t.status <> 'Cancelled'
                              AND b.status <> 'Cancelled'
                        ),
                        0
                    ) AS revenue,
                    COALESCE(
                        (
                            SELECT ROUND(AVG(load_factor), 1)
                            FROM (
                                SELECT
                                    100.0 * COUNT(t.ticket_id) FILTER (
                                        WHERE t.status <> 'Cancelled'
                                    ) / NULLIF(COUNT(DISTINCT s.seat_id), 0) AS load_factor
                                FROM flight f
                                JOIN seat s ON s.aircraft_id = f.aircraft_id
                                LEFT JOIN ticket t
                                    ON t.flight_id = f.flight_id
                                   AND t.seat_id = s.seat_id
                                   AND t.status <> 'Cancelled'
                                WHERE f.departure_time > CURRENT_TIMESTAMP
                                  AND f.status IN ('Scheduled', 'Boarding')
                                GROUP BY f.flight_id
                            ) load_stats
                        ),
                        0
                    ) AS average_load;
            """)
            stats = cur.fetchone()

            cur.execute("""
                SELECT
                    b.booking_reference,
                    b.booked_at,
                    b.status,
                    p.first_name,
                    p.last_name,
                    f.flight_number,
                    origin.iata_code AS origin,
                    destination.iata_code AS destination,
                    t.price
                FROM booking b
                JOIN passenger p ON p.passenger_id = b.passenger_id
                LEFT JOIN ticket t ON t.booking_id = b.booking_id
                LEFT JOIN flight f ON f.flight_id = t.flight_id
                LEFT JOIN route r ON r.route_id = f.route_id
                LEFT JOIN airport origin ON origin.airport_id = r.origin_airport_id
                LEFT JOIN airport destination ON destination.airport_id = r.destination_airport_id
                ORDER BY b.booked_at DESC, b.booking_id DESC
                LIMIT 6;
            """)
            recent_bookings = cur.fetchall()

            # Booking activity for the last 14 calendar days.
            cur.execute("""
                SELECT
                    days.day::date AS day,
                    COUNT(b.booking_id) AS bookings
                FROM generate_series(
                    CURRENT_DATE - INTERVAL '13 days',
                    CURRENT_DATE,
                    INTERVAL '1 day'
                ) AS days(day)
                LEFT JOIN booking b
                    ON b.booked_at::date = days.day::date
                GROUP BY days.day
                ORDER BY days.day;
            """)
            trend_rows = cur.fetchall()

            # Route ranking: real bookings and ticket revenue from PostgreSQL.
            cur.execute("""
                SELECT
                    origin.iata_code AS origin,
                    destination.iata_code AS destination,
                    COUNT(DISTINCT b.booking_id) FILTER (
                        WHERE b.status <> 'Cancelled'
                    ) AS bookings,
                    COALESCE(
                        SUM(t.price) FILTER (
                            WHERE t.status <> 'Cancelled'
                              AND b.status <> 'Cancelled'
                        ),
                        0
                    ) AS revenue
                FROM route r
                JOIN airport origin
                    ON origin.airport_id = r.origin_airport_id
                JOIN airport destination
                    ON destination.airport_id = r.destination_airport_id
                JOIN flight f
                    ON f.route_id = r.route_id
                LEFT JOIN ticket t
                    ON t.flight_id = f.flight_id
                LEFT JOIN booking b
                    ON b.booking_id = t.booking_id
                GROUP BY
                    r.route_id,
                    origin.iata_code,
                    destination.iata_code
                HAVING COUNT(DISTINCT b.booking_id) FILTER (
                    WHERE b.status <> 'Cancelled'
                ) > 0
                ORDER BY bookings DESC, revenue DESC
                LIMIT 6;
            """)
            route_rows = cur.fetchall()

            cur.execute("""
                SELECT status, COUNT(*) AS total
                FROM booking
                GROUP BY status
                ORDER BY total DESC, status;
            """)
            status_rows = cur.fetchall()

            # Upcoming load factor for the next six flights.
            cur.execute("""
                SELECT
                    f.flight_id,
                    f.flight_number,
                    origin.iata_code AS origin,
                    destination.iata_code AS destination,
                    f.departure_time,
                    COUNT(DISTINCT s.seat_id) AS total_seats,
                    COUNT(DISTINCT t.seat_id) FILTER (
                        WHERE t.status <> 'Cancelled'
                    ) AS booked_seats,
                    ROUND(
                        100.0 * COUNT(DISTINCT t.seat_id) FILTER (
                            WHERE t.status <> 'Cancelled'
                        ) / NULLIF(COUNT(DISTINCT s.seat_id), 0),
                        1
                    ) AS occupancy
                FROM flight f
                JOIN route r ON r.route_id = f.route_id
                JOIN airport origin ON origin.airport_id = r.origin_airport_id
                JOIN airport destination ON destination.airport_id = r.destination_airport_id
                JOIN seat s ON s.aircraft_id = f.aircraft_id
                LEFT JOIN ticket t
                    ON t.flight_id = f.flight_id
                   AND t.seat_id = s.seat_id
                   AND t.status <> 'Cancelled'
                WHERE f.departure_time > CURRENT_TIMESTAMP
                  AND f.status IN ('Scheduled', 'Boarding')
                GROUP BY
                    f.flight_id,
                    f.flight_number,
                    origin.iata_code,
                    destination.iata_code,
                    f.departure_time
                ORDER BY f.departure_time
                LIMIT 6;
            """)
            occupancy_rows = cur.fetchall()

    analytics = {
        "trend": [
            {
                "label": row["day"].strftime("%d.%m"),
                "value": int(row["bookings"] or 0)
            }
            for row in trend_rows
        ],
        "routes": [
            {
                "label": f"{row['origin']} → {row['destination']}",
                "bookings": int(row["bookings"] or 0),
                "revenue": float(row["revenue"] or 0)
            }
            for row in route_rows
        ],
        "statuses": [
            {
                "label": row["status"],
                "value": int(row["total"] or 0)
            }
            for row in status_rows
        ],
        "occupancy": [
            {
                "flight_number": row["flight_number"],
                "route": f"{row['origin']} → {row['destination']}",
                "departure": row["departure_time"].strftime("%d.%m %H:%M"),
                "booked": int(row["booked_seats"] or 0),
                "total": int(row["total_seats"] or 0),
                "percent": float(row["occupancy"] or 0)
            }
            for row in occupancy_rows
        ]
    }

    return render_template(
        "dashboard.html",
        stats=stats,
        recent_bookings=recent_bookings,
        analytics=analytics
    )


@app.route("/")
def home():
    selected_destination = request.args.get("destination_id", type=int)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT airport_id, city, iata_code, country
                FROM airport
                ORDER BY city, iata_code;
            """)
            airports = cur.fetchall()

    return render_template(
        "home.html",
        airports=airports,
        today=date.today(),
        selected_destination=selected_destination
    )


@app.route("/journey")
def journey():
    """Cinematic destination reel built from airports/routes in PostgreSQL."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    a.city,
                    a.country,
                    a.iata_code,
                    COUNT(f.flight_id) AS future_flights
                FROM airport a
                LEFT JOIN route r
                    ON r.destination_airport_id = a.airport_id
                LEFT JOIN flight f
                    ON f.route_id = r.route_id
                   AND f.departure_time > CURRENT_TIMESTAMP
                   AND f.status IN ('Scheduled', 'Boarding')
                WHERE a.city IS NOT NULL
                  AND a.country IS NOT NULL
                GROUP BY a.airport_id, a.city, a.country, a.iata_code
                ORDER BY COUNT(f.flight_id) DESC, a.city, a.iata_code
                LIMIT 10;
            """)
            cities = cur.fetchall()

    return render_template("journey.html", cities=cities)




@app.route("/globe")
def flight_globe():
    """Interactive 3D visualization of the route network stored in PostgreSQL."""
    return render_template("globe.html")


@app.route("/api/globe-data")
def globe_data():
    """Return airports, route arcs and flights for the interactive globe."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT airport_id, iata_code, city, country
                FROM airport
                ORDER BY city, iata_code;
            """)
            airport_rows = cur.fetchall()

            # Draw only routes that actually have a flight in the globe time window.
            # The database contains every airport pair (50 * 49 = 2450 routes), and
            # rendering thousands of animated 3D tubes can stall WebGL completely.
            cur.execute("""
                SELECT
                    r.route_id,
                    r.distance_km,
                    origin.iata_code AS origin_iata,
                    origin.city AS origin_city,
                    origin.country AS origin_country,
                    destination.iata_code AS destination_iata,
                    destination.city AS destination_city,
                    destination.country AS destination_country,
                    COUNT(f.flight_id) AS upcoming_flights
                FROM route r
                JOIN airport origin
                    ON origin.airport_id = r.origin_airport_id
                JOIN airport destination
                    ON destination.airport_id = r.destination_airport_id
                JOIN flight f
                    ON f.route_id = r.route_id
                WHERE f.status <> 'Cancelled'
                  AND f.arrival_time >= CURRENT_TIMESTAMP - INTERVAL '12 hours'
                  AND f.departure_time <= CURRENT_TIMESTAMP + INTERVAL '14 days'
                GROUP BY
                    r.route_id, r.distance_km,
                    origin.iata_code, origin.city, origin.country,
                    destination.iata_code, destination.city, destination.country
                ORDER BY upcoming_flights DESC, origin.iata_code, destination.iata_code
                LIMIT 120;
            """)
            route_rows = cur.fetchall()

            cur.execute("""
                SELECT
                    f.flight_id,
                    f.flight_number,
                    f.departure_time,
                    f.arrival_time,
                    f.status,
                    a.model,
                    a.registration_number,
                    origin.iata_code AS origin_iata,
                    origin.city AS origin_city,
                    destination.iata_code AS destination_iata,
                    destination.city AS destination_city
                FROM flight f
                JOIN route r ON r.route_id = f.route_id
                JOIN airport origin ON origin.airport_id = r.origin_airport_id
                JOIN airport destination ON destination.airport_id = r.destination_airport_id
                JOIN aircraft a ON a.aircraft_id = f.aircraft_id
                WHERE f.status <> 'Cancelled'
                  AND f.arrival_time >= CURRENT_TIMESTAMP - INTERVAL '12 hours'
                  AND f.departure_time <= CURRENT_TIMESTAMP + INTERVAL '14 days'
                ORDER BY
                    CASE f.status
                        WHEN 'Departed' THEN 0
                        WHEN 'Boarding' THEN 1
                        WHEN 'Scheduled' THEN 2
                        WHEN 'Arrived' THEN 3
                        ELSE 4
                    END,
                    f.departure_time
                LIMIT 80;
            """)
            flight_rows = cur.fetchall()

    airport_items = []
    airport_lookup = {}
    unmapped = []

    for row in airport_rows:
        code = (row["iata_code"] or "").upper()
        coords = AIRPORT_GLOBE_COORDINATES.get(code)
        if not coords:
            unmapped.append({
                "iata": code,
                "city": row["city"],
                "country": row["country"],
            })
            continue

        item = {
            "airport_id": row["airport_id"],
            "iata": code,
            "city": row["city"],
            "country": row["country"],
            "lat": coords[0],
            "lng": coords[1],
            "route_count": 0,
            "flight_count": 0,
        }
        airport_items.append(item)
        airport_lookup[code] = item

    route_items = []
    for row in route_rows:
        origin_code = (row["origin_iata"] or "").upper()
        destination_code = (row["destination_iata"] or "").upper()
        origin = airport_lookup.get(origin_code)
        destination = airport_lookup.get(destination_code)
        if not origin or not destination:
            continue

        origin["route_count"] += 1
        destination["route_count"] += 1

        route_items.append({
            "route_id": row["route_id"],
            "origin_iata": origin_code,
            "origin_city": row["origin_city"],
            "origin_country": row["origin_country"],
            "destination_iata": destination_code,
            "destination_city": row["destination_city"],
            "destination_country": row["destination_country"],
            "start_lat": origin["lat"],
            "start_lng": origin["lng"],
            "end_lat": destination["lat"],
            "end_lng": destination["lng"],
            "distance_km": float(row["distance_km"]) if row["distance_km"] is not None else None,
            "upcoming_flights": int(row["upcoming_flights"] or 0),
        })

    flight_items = []
    for row in flight_rows:
        origin_code = (row["origin_iata"] or "").upper()
        destination_code = (row["destination_iata"] or "").upper()
        origin = airport_lookup.get(origin_code)
        destination = airport_lookup.get(destination_code)
        if not origin or not destination:
            continue

        origin["flight_count"] += 1
        destination["flight_count"] += 1

        flight_items.append({
            "flight_id": row["flight_id"],
            "flight_number": row["flight_number"],
            "status": row["status"],
            "model": row["model"],
            "registration_number": row["registration_number"],
            "departure_time": row["departure_time"].isoformat(timespec="seconds"),
            "arrival_time": row["arrival_time"].isoformat(timespec="seconds"),
            "origin_iata": origin_code,
            "origin_city": row["origin_city"],
            "destination_iata": destination_code,
            "destination_city": row["destination_city"],
            "start_lat": origin["lat"],
            "start_lng": origin["lng"],
            "end_lat": destination["lat"],
            "end_lng": destination["lng"],
        })

    return jsonify({
        "airports": airport_items,
        "routes": route_items,
        "flights": flight_items,
        "unmapped_airports": unmapped,
    })


@app.route("/destinations")
def destinations():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    destination.airport_id,
                    destination.iata_code,
                    destination.city,
                    destination.country,
                    COUNT(DISTINCT f.flight_id) AS future_flights,
                    MIN(
                        ROUND(
                            (12000 + r.distance_km * 8) *
                            CASE s.seat_class
                                WHEN 'Business' THEN 1.8
                                WHEN 'First' THEN 2.5
                                ELSE 1
                            END,
                            2
                        )
                    ) AS min_price
                FROM flight f
                JOIN route r
                    ON r.route_id = f.route_id
                JOIN airport destination
                    ON destination.airport_id = r.destination_airport_id
                JOIN seat s
                    ON s.aircraft_id = f.aircraft_id
                WHERE f.departure_time > CURRENT_TIMESTAMP
                  AND f.status IN ('Scheduled', 'Boarding')
                  AND NOT EXISTS (
                      SELECT 1
                      FROM ticket t
                      WHERE t.flight_id = f.flight_id
                        AND t.seat_id = s.seat_id
                        AND t.status <> 'Cancelled'
                  )
                GROUP BY
                    destination.airport_id,
                    destination.iata_code,
                    destination.city,
                    destination.country
                ORDER BY destination.city, destination.iata_code;
            """)
            rows = cur.fetchall()

    destination_list = []

    for row in rows:
        item = dict(row)
        info = DESTINATION_INFO.get(item["iata_code"], {})

        item["description"] = info.get(
            "description",
            f"{item['city']} — одно из доступных направлений вашей авиасистемы."
        )

        item["highlights"] = info.get(
            "highlights",
            ["Путешествия", "Город", "Новые впечатления"]
        )

        if item["min_price"] is not None:
            item["min_price"] = float(item["min_price"])

        destination_list.append(item)

    return render_template(
        "destinations.html",
        destinations=destination_list
    )


@app.route("/destinations/<iata_code>")
def destination_detail(iata_code):
    iata_code = iata_code.strip().upper()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT airport_id, city, iata_code, country
                FROM airport
                WHERE UPPER(iata_code) = %s;
            """, (iata_code,))
            airport = cur.fetchone()

            if not airport:
                abort(404)

            cur.execute("""
                SELECT
                    COUNT(DISTINCT f.flight_id) AS future_flights,
                    COUNT(DISTINCT r.origin_airport_id) AS origin_count,
                    MIN(
                        ROUND(
                            (12000 + r.distance_km * 8) *
                            CASE s.seat_class
                                WHEN 'Business' THEN 1.8
                                WHEN 'First' THEN 2.5
                                ELSE 1
                            END,
                            2
                        )
                    ) AS min_price
                FROM flight f
                JOIN route r ON r.route_id = f.route_id
                JOIN seat s ON s.aircraft_id = f.aircraft_id
                WHERE r.destination_airport_id = %s
                  AND f.departure_time > CURRENT_TIMESTAMP
                  AND f.status IN ('Scheduled', 'Boarding')
                  AND NOT EXISTS (
                      SELECT 1
                      FROM ticket t
                      WHERE t.flight_id = f.flight_id
                        AND t.seat_id = s.seat_id
                        AND t.status <> 'Cancelled'
                  );
            """, (airport["airport_id"],))
            stats = cur.fetchone()

            cur.execute("""
                SELECT
                    f.flight_id,
                    f.flight_number,
                    f.departure_time,
                    f.arrival_time,
                    a.model,
                    origin.city AS origin_city,
                    origin.iata_code AS origin_code,
                    seats.available_count,
                    seats.min_price
                FROM flight f
                JOIN route r ON r.route_id = f.route_id
                JOIN airport origin ON origin.airport_id = r.origin_airport_id
                JOIN aircraft a ON a.aircraft_id = f.aircraft_id
                CROSS JOIN LATERAL (
                    SELECT
                        COUNT(*) AS available_count,
                        MIN(
                            ROUND(
                                (12000 + r.distance_km * 8) *
                                CASE s.seat_class
                                    WHEN 'Business' THEN 1.8
                                    WHEN 'First' THEN 2.5
                                    ELSE 1
                                END,
                                2
                            )
                        ) AS min_price
                    FROM seat s
                    WHERE s.aircraft_id = f.aircraft_id
                      AND NOT EXISTS (
                          SELECT 1
                          FROM ticket t
                          WHERE t.flight_id = f.flight_id
                            AND t.seat_id = s.seat_id
                            AND t.status <> 'Cancelled'
                      )
                ) seats
                WHERE r.destination_airport_id = %s
                  AND f.departure_time > CURRENT_TIMESTAMP
                  AND f.status IN ('Scheduled', 'Boarding')
                  AND seats.available_count > 0
                ORDER BY f.departure_time
                LIMIT 5;
            """, (airport["airport_id"],))
            next_flights = cur.fetchall()

    info = DESTINATION_INFO.get(iata_code, {})
    highlights = info.get(
        "highlights",
        ["Центр города", "Местная кухня", "Новые впечатления"]
    )

    guide = {
        "description": info.get(
            "description",
            f"{airport['city']} — направление, доступное в вашей авиасистеме."
        ),
        "highlights": highlights,
        "ideal_days": info.get("ideal_days", "2–4 дня"),
        "pace": info.get(
            "pace",
            "смешанный: прогулки, достопримечательности и свободное время"
        ),
        "itinerary": info.get("itinerary") or [
            {
                "time": "Утро",
                "title": f"Начните с: {highlights[0]}",
                "text": "Приезжайте пораньше, пока меньше людей, и спокойно познакомьтесь с районом."
            },
            {
                "time": "День",
                "title": f"Главная точка: {highlights[1] if len(highlights) > 1 else highlights[0]}",
                "text": "Оставьте несколько часов без жёсткого расписания: так маршрут ощущается как поездка, а не чек-лист."
            },
            {
                "time": "Вечер",
                "title": f"Финиш дня: {highlights[2] if len(highlights) > 2 else highlights[-1]}",
                "text": "Завершите день прогулкой и местной кухней рядом с центральным районом."
            }
        ],
        "tips": info.get("tips") or [
            "Перед поездкой проверьте актуальные визовые и въездные требования.",
            "Сохраните офлайн-карту и адрес вашего проживания до вылета.",
            "Оставляйте запас времени на дорогу в аэропорт и прохождение контроля.",
            "Цены и часы работы достопримечательностей лучше перепроверять перед посещением."
        ]
    }

    detail_stats = dict(stats or {})
    if detail_stats.get("min_price") is not None:
        detail_stats["min_price"] = float(detail_stats["min_price"])

    prepared_flights = []
    for flight in next_flights:
        item = dict(flight)
        if item.get("min_price") is not None:
            item["min_price"] = float(item["min_price"])
        prepared_flights.append(item)

    return render_template(
        "destination_detail.html",
        airport=airport,
        guide=guide,
        stats=detail_stats,
        next_flights=prepared_flights
    )


@app.route("/search")

def search_flights():

    origin_id = request.args.get("origin_id", type=int)

    destination_id = request.args.get("destination_id", type=int)

    departure_date_raw = request.args.get("departure_date", "")



    try:

        departure_date = date.fromisoformat(departure_date_raw)

    except ValueError:

        departure_date = None



    error = None

    if not origin_id or not destination_id or not departure_date:

        error = "Выберите аэропорты вылета и прилёта и дату."

    elif origin_id == destination_id:

        error = "Аэропорты вылета и прилёта должны различаться."



    if error:

        flash(error)

        return redirect(url_for("home"))



    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("""

                SELECT airport_id, city, iata_code

                FROM airport WHERE airport_id IN (%s, %s);

            """, (origin_id, destination_id))

            airports = {a["airport_id"]: a for a in cur.fetchall()}



            if origin_id not in airports or destination_id not in airports:

                flash("Выбранный аэропорт не найден.")

                return redirect(url_for("home"))



            cur.execute("""

                SELECT f.flight_id, f.flight_number, f.departure_time,

                       f.arrival_time, f.status, a.model,

                       origin.city AS origin_city, origin.iata_code AS origin_code,

                       destination.city AS destination_city,

                       destination.iata_code AS destination_code,

                       seats.available_count, seats.min_price

                FROM flight f

                JOIN route r ON r.route_id = f.route_id

                JOIN airport origin ON origin.airport_id = r.origin_airport_id

                JOIN airport destination ON destination.airport_id = r.destination_airport_id

                JOIN aircraft a ON a.aircraft_id = f.aircraft_id

                CROSS JOIN LATERAL (

                    SELECT COUNT(*) AS available_count,

                           MIN(ROUND((12000 + r.distance_km * 8) *

                               CASE s.seat_class

                                   WHEN 'Business' THEN 1.8

                                   WHEN 'First' THEN 2.5

                                   ELSE 1

                               END, 2)) AS min_price

                    FROM seat s

                    WHERE s.aircraft_id = f.aircraft_id

                      AND NOT EXISTS (

                          SELECT 1 FROM ticket t

                          WHERE t.flight_id = f.flight_id AND t.seat_id = s.seat_id
                                  AND t.status <> 'Cancelled'

                      )

                ) seats

                WHERE r.origin_airport_id = %s

                  AND r.destination_airport_id = %s

                  AND f.departure_time >= %s::date

                  AND f.departure_time < %s::date + INTERVAL '1 day'

                  AND f.departure_time > CURRENT_TIMESTAMP

                  AND f.status IN ('Scheduled', 'Boarding')

                  AND seats.available_count >= 1

                ORDER BY f.departure_time, seats.min_price;

            """, (origin_id, destination_id, departure_date, departure_date))

            results = cur.fetchall()



    return render_template(

        "search_results.html", flights=results,

        origin=airports[origin_id], destination=airports[destination_id],

        departure_date=departure_date

    )





@app.route("/book/<int:flight_id>", methods=["GET", "POST"])

def book_flight(flight_id):

    error = None

    if request.method == "POST":

        check_csrf()

        seat_id = request.form.get("seat_id", type=int)

        first_name = request.form.get("first_name", "").strip()

        last_name = request.form.get("last_name", "").strip()

        passport = request.form.get("passport_number", "").strip().upper()

        dob_text = request.form.get("date_of_birth", "")

        email = request.form.get("email", "").strip() or None

        phone = request.form.get("phone", "").strip() or None

        try:

            dob = date.fromisoformat(dob_text)

        except ValueError:

            dob = None



        if (not seat_id or not first_name or not last_name or not passport

                or not dob or dob >= date.today()

                or len(first_name) > 50 or len(last_name) > 50

                or len(passport) > 20 or (email and len(email) > 100)

                or (phone and len(phone) > 20)):

            error = "Проверьте место и данные пассажира."

        else:

            try:

                with get_connection() as conn:

                    with conn.cursor() as cur:

                        # Locks the flight row; the unique flight/seat constraint

                        # is the final guard against concurrent bookings.

                        cur.execute("""

                            SELECT s.seat_id,

                                   ROUND((12000 + r.distance_km * 8) *

                                       CASE s.seat_class

                                           WHEN 'Business' THEN 1.8

                                           WHEN 'First' THEN 2.5

                                           ELSE 1 END, 2) AS price

                            FROM flight f

                            JOIN route r ON r.route_id = f.route_id

                            JOIN seat s ON s.aircraft_id = f.aircraft_id

                            WHERE f.flight_id = %s AND s.seat_id = %s

                              AND f.status IN ('Scheduled', 'Boarding')

                              AND f.departure_time > CURRENT_TIMESTAMP

                              AND NOT EXISTS (

                                  SELECT 1 FROM ticket t

                                  WHERE t.flight_id = f.flight_id AND t.seat_id = s.seat_id
                                  AND t.status <> 'Cancelled'

                              )

                            FOR UPDATE OF f;

                        """, (flight_id, seat_id))

                        selected = cur.fetchone()

                        if not selected:

                            raise ValueError("Место уже занято или рейс недоступен.")



                        cur.execute("""

                            SELECT passenger_id, first_name, last_name, date_of_birth

                            FROM passenger WHERE passport_number = %s;

                        """, (passport,))

                        passenger = cur.fetchone()

                        if passenger:

                            if (passenger["first_name"].casefold() != first_name.casefold()

                                    or passenger["last_name"].casefold() != last_name.casefold()

                                    or passenger["date_of_birth"] != dob):

                                raise ValueError("Паспорт уже указан с другими данными пассажира.")

                            passenger_id = passenger["passenger_id"]

                        else:

                            cur.execute("""

                                INSERT INTO passenger

                                    (first_name, last_name, date_of_birth, email, phone, passport_number)

                                VALUES (%s, %s, %s, %s, %s, %s)

                                RETURNING passenger_id;

                            """, (first_name, last_name, dob, email, phone, passport))

                            passenger_id = cur.fetchone()["passenger_id"]



                        reference = "BK" + uuid.uuid4().hex[:16].upper()

                        ticket_number = "TKT" + uuid.uuid4().hex[:16].upper()

                        cur.execute("""

                            INSERT INTO booking (passenger_id, booking_reference, status)

                            VALUES (%s, %s, 'Confirmed') RETURNING booking_id;

                        """, (passenger_id, reference))

                        booking_id = cur.fetchone()["booking_id"]

                        cur.execute("""

                            INSERT INTO ticket

                                (booking_id, flight_id, seat_id, ticket_number, price, status)

                            VALUES (%s, %s, %s, %s, %s, 'Issued');

                        """, (booking_id, flight_id, seat_id, ticket_number, selected["price"]))



                session["last_booking_reference"] = reference

                return redirect(url_for("booking_confirmation", reference=reference))

            except ValueError as exc:

                error = str(exc)

            except psycopg.errors.UniqueViolation:

                error = "Место уже занято или номер паспорта указан с другими данными."



    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("""

                SELECT f.flight_id, f.flight_number, f.departure_time,

                       origin.city AS origin_city, destination.city AS destination_city

                FROM flight f

                JOIN route r ON r.route_id = f.route_id

                JOIN airport origin ON origin.airport_id = r.origin_airport_id

                JOIN airport destination ON destination.airport_id = r.destination_airport_id

                WHERE f.flight_id = %s AND f.status IN ('Scheduled', 'Boarding')

                  AND f.departure_time > CURRENT_TIMESTAMP;

            """, (flight_id,))

            flight = cur.fetchone()

    if not flight:

        abort(404)

    return render_template("customer_booking.html", flight=flight, error=error)





@app.route("/confirmation/<reference>")

def booking_confirmation(reference):

    if not hmac.compare_digest(reference, session.get("last_booking_reference", "-")):

        abort(404)

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("""

                SELECT b.booking_reference, b.status, p.first_name, p.last_name,

                       f.flight_number, f.departure_time, f.arrival_time,

                       origin.city AS origin_city, destination.city AS destination_city,

                       s.seat_number, s.seat_class, t.ticket_number, t.price

                FROM booking b

                JOIN passenger p ON p.passenger_id = b.passenger_id

                JOIN ticket t ON t.booking_id = b.booking_id

                JOIN seat s ON s.seat_id = t.seat_id

                JOIN flight f ON f.flight_id = t.flight_id

                JOIN route r ON r.route_id = f.route_id

                JOIN airport origin ON origin.airport_id = r.origin_airport_id

                JOIN airport destination ON destination.airport_id = r.destination_airport_id

                WHERE b.booking_reference = %s;

            """, (reference,))

            booking = cur.fetchone()

    if not booking:

        abort(404)

    response = app.make_response(render_template("confirmation.html", booking=booking))

    response.headers["Cache-Control"] = "no-store"

    return response





# =========================================================
# PUBLIC BOOKING MANAGEMENT
# =========================================================


def _lookup_public_booking(reference, last_name):
    """Return one booking only when reference + passenger surname both match."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    b.booking_id,
                    b.booking_reference,
                    b.booked_at,
                    b.status AS booking_status,
                    p.first_name,
                    p.last_name,
                    p.email,
                    p.phone,
                    p.passport_number,
                    t.ticket_id,
                    t.ticket_number,
                    t.price,
                    t.status AS ticket_status,
                    f.flight_id,
                    f.flight_number,
                    f.departure_time,
                    f.arrival_time,
                    f.status AS flight_status,
                    origin.city AS origin_city,
                    origin.iata_code AS origin_code,
                    destination.city AS destination_city,
                    destination.iata_code AS destination_code,
                    s.seat_number,
                    s.seat_class,
                    CASE
                        WHEN b.status IN ('Pending', 'Confirmed')
                         AND (f.departure_time IS NULL OR f.departure_time > CURRENT_TIMESTAMP)
                         AND COALESCE(f.status, 'Scheduled') <> 'Cancelled'
                        THEN TRUE
                        ELSE FALSE
                    END AS can_cancel
                FROM booking b
                JOIN passenger p
                    ON p.passenger_id = b.passenger_id
                LEFT JOIN ticket t
                    ON t.booking_id = b.booking_id
                LEFT JOIN flight f
                    ON f.flight_id = t.flight_id
                LEFT JOIN route r
                    ON r.route_id = f.route_id
                LEFT JOIN airport origin
                    ON origin.airport_id = r.origin_airport_id
                LEFT JOIN airport destination
                    ON destination.airport_id = r.destination_airport_id
                LEFT JOIN seat s
                    ON s.seat_id = t.seat_id
                WHERE UPPER(b.booking_reference) = UPPER(%s)
                  AND LOWER(p.last_name) = LOWER(%s)
                ORDER BY t.ticket_id NULLS LAST
                LIMIT 1;
            """, (reference, last_name))
            return cur.fetchone()


@app.route("/manage-booking", methods=["GET", "POST"])
def manage_booking():
    error = None

    if request.args.get("new") == "1":
        session.pop("managed_booking", None)
        return redirect(url_for("manage_booking"))

    if request.method == "POST":
        check_csrf()
        reference = request.form.get("booking_reference", "").strip().upper()
        last_name = request.form.get("last_name", "").strip()

        if not reference or not last_name:
            error = "Введите номер брони и фамилию пассажира."
        else:
            booking = _lookup_public_booking(reference, last_name)
            if booking:
                session["managed_booking"] = {
                    "reference": reference,
                    "last_name": last_name
                }
                return redirect(url_for("manage_booking"))

            error = "Бронирование не найдено. Проверьте номер брони и фамилию."

    booking = None
    lookup = session.get("managed_booking")
    if lookup:
        booking = _lookup_public_booking(
            lookup.get("reference", ""),
            lookup.get("last_name", "")
        )
        if not booking:
            session.pop("managed_booking", None)

    response = app.make_response(
        render_template(
            "manage_booking.html",
            booking=booking,
            error=error
        )
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/manage-booking/cancel")
def cancel_public_booking():
    check_csrf()

    lookup = session.get("managed_booking")
    if not lookup:
        flash("Сначала найдите бронирование.")
        return redirect(url_for("manage_booking"))

    reference = lookup.get("reference", "")
    last_name = lookup.get("last_name", "")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    b.booking_id,
                    b.status,
                    f.departure_time,
                    f.status AS flight_status
                FROM booking b
                JOIN passenger p
                    ON p.passenger_id = b.passenger_id
                LEFT JOIN ticket t
                    ON t.booking_id = b.booking_id
                LEFT JOIN flight f
                    ON f.flight_id = t.flight_id
                WHERE UPPER(b.booking_reference) = UPPER(%s)
                  AND LOWER(p.last_name) = LOWER(%s)
                ORDER BY t.ticket_id NULLS LAST
                LIMIT 1
                FOR UPDATE OF b;
            """, (reference, last_name))
            booking = cur.fetchone()

            if not booking:
                session.pop("managed_booking", None)
                flash("Бронирование не найдено.")
                return redirect(url_for("manage_booking"))

            if booking["status"] == "Cancelled":
                flash("Это бронирование уже отменено.")
                return redirect(url_for("manage_booking"))

            if booking["departure_time"] and booking["departure_time"] <= datetime.now():
                flash("После времени вылета бронирование отменить нельзя.")
                return redirect(url_for("manage_booking"))

            if booking["flight_status"] in ("Departed", "Arrived", "Cancelled"):
                flash("Этот рейс уже нельзя отменить через клиентский кабинет.")
                return redirect(url_for("manage_booking"))

            cur.execute("""
                UPDATE booking
                SET status = 'Cancelled'
                WHERE booking_id = %s;
            """, (booking["booking_id"],))

            cur.execute("""
                UPDATE ticket
                SET status = 'Cancelled'
                WHERE booking_id = %s
                  AND status <> 'Cancelled';
            """, (booking["booking_id"],))

            cur.execute("""
                UPDATE payment
                SET status = 'Refunded'
                WHERE booking_id = %s
                  AND status = 'Completed';
            """, (booking["booking_id"],))

    flash("Бронирование отменено. Место снова доступно для продажи.")
    return redirect(url_for("manage_booking"))


# =========================================================

# FLIGHTS

# =========================================================



@app.route("/admin/flights")
def flights():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    f.flight_id,
                    f.flight_number,
                    origin.iata_code AS origin,
                    destination.iata_code AS destination,
                    f.departure_time,
                    f.arrival_time,
                    f.status,
                    a.model,
                    a.registration_number,
                    (
                        SELECT COUNT(*)
                        FROM seat s
                        WHERE s.aircraft_id = f.aircraft_id
                    ) AS total_seats,
                    (
                        SELECT COUNT(*)
                        FROM ticket t
                        WHERE t.flight_id = f.flight_id
                          AND t.status <> 'Cancelled'
                    ) AS booked_seats
                FROM flight f
                JOIN route r
                    ON f.route_id = r.route_id
                JOIN airport origin
                    ON r.origin_airport_id = origin.airport_id
                JOIN airport destination
                    ON r.destination_airport_id = destination.airport_id
                JOIN aircraft a
                    ON f.aircraft_id = a.aircraft_id
                ORDER BY f.departure_time DESC;
            """)
            flight_list = cur.fetchall()

    return render_template(
        "flights.html",
        flights=flight_list
    )


def _flight_form_options():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    r.route_id,
                    origin.iata_code AS origin_code,
                    origin.city AS origin_city,
                    destination.iata_code AS destination_code,
                    destination.city AS destination_city,
                    r.distance_km,
                    r.estimated_duration_minutes
                FROM route r
                JOIN airport origin
                    ON origin.airport_id = r.origin_airport_id
                JOIN airport destination
                    ON destination.airport_id = r.destination_airport_id
                ORDER BY origin.iata_code, destination.iata_code;
            """)
            routes = cur.fetchall()

            cur.execute("""
                SELECT
                    a.aircraft_id,
                    a.registration_number,
                    a.manufacturer,
                    a.model,
                    a.in_service,
                    COUNT(s.seat_id) AS seat_count
                FROM aircraft a
                LEFT JOIN seat s
                    ON s.aircraft_id = a.aircraft_id
                GROUP BY
                    a.aircraft_id,
                    a.registration_number,
                    a.manufacturer,
                    a.model,
                    a.in_service
                ORDER BY a.in_service DESC, a.model, a.registration_number;
            """)
            aircraft = cur.fetchall()

    return routes, aircraft


def _parse_flight_form():
    flight_number = request.form.get("flight_number", "").strip().upper()
    route_id = request.form.get("route_id", type=int)
    aircraft_id = request.form.get("aircraft_id", type=int)
    departure_raw = request.form.get("departure_time", "").strip()
    arrival_raw = request.form.get("arrival_time", "").strip()
    status = request.form.get("status", "Scheduled").strip()

    try:
        departure_time = datetime.fromisoformat(departure_raw)
        arrival_time = datetime.fromisoformat(arrival_raw)
    except ValueError:
        departure_time = None
        arrival_time = None

    allowed_statuses = {"Scheduled", "Boarding", "Departed", "Arrived"}

    if not flight_number or len(flight_number) > 10:
        return None, "Номер рейса обязателен и должен быть не длиннее 10 символов."
    if not route_id or not aircraft_id:
        return None, "Выберите маршрут и самолёт."
    if not departure_time or not arrival_time or arrival_time <= departure_time:
        return None, "Время прилёта должно быть позже времени вылета."
    if status not in allowed_statuses:
        return None, "Некорректный статус рейса."

    return {
        "flight_number": flight_number,
        "route_id": route_id,
        "aircraft_id": aircraft_id,
        "departure_time": departure_time,
        "arrival_time": arrival_time,
        "status": status
    }, None


@app.route("/admin/flights/new", methods=["GET", "POST"])
def create_flight():
    error = None

    if request.method == "POST":
        check_csrf()
        data, error = _parse_flight_form()

        if data and data["departure_time"] <= datetime.now():
            error = "Новый рейс должен вылетать в будущем."
            data = None

        if data:
            try:
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT 1
                            FROM aircraft
                            WHERE aircraft_id = %s
                              AND in_service = TRUE
                              AND EXISTS (
                                  SELECT 1 FROM seat s
                                  WHERE s.aircraft_id = aircraft.aircraft_id
                              );
                        """, (data["aircraft_id"],))
                        if not cur.fetchone():
                            raise ValueError("Выбранный самолёт сейчас не находится в эксплуатации.")

                        cur.execute("""
                            INSERT INTO flight (
                                route_id,
                                aircraft_id,
                                flight_number,
                                departure_time,
                                arrival_time,
                                status
                            )
                            VALUES (%s, %s, %s, %s, %s, %s);
                        """, (
                            data["route_id"],
                            data["aircraft_id"],
                            data["flight_number"],
                            data["departure_time"],
                            data["arrival_time"],
                            data["status"]
                        ))

                flash(f"Рейс {data['flight_number']} создан.")
                return redirect(url_for("flights"))
            except ValueError as exc:
                error = str(exc)
            except psycopg.errors.UniqueViolation:
                error = "Рейс с таким номером и временем вылета уже существует."
            except psycopg.errors.ForeignKeyViolation:
                error = "Выбранный маршрут или самолёт больше не существует."
            except psycopg.errors.CheckViolation:
                error = "Проверьте время и статус рейса."

    routes, aircraft = _flight_form_options()
    return render_template(
        "flight_form.html",
        mode="create",
        flight=None,
        routes=routes,
        aircraft=aircraft,
        error=error
    )


@app.route("/admin/flights/<int:flight_id>/edit", methods=["GET", "POST"])
def edit_flight(flight_id):
    error = None

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    f.*,
                    (
                        SELECT COUNT(*)
                        FROM ticket t
                        WHERE t.flight_id = f.flight_id
                    ) AS ticket_count
                FROM flight f
                WHERE f.flight_id = %s;
            """, (flight_id,))
            flight = cur.fetchone()

    if not flight:
        abort(404)

    if request.method == "POST":
        check_csrf()
        data, error = _parse_flight_form()

        if data:
            if flight["status"] == "Cancelled":
                error = "Отменённый рейс нельзя снова редактировать. Создайте новый рейс."
            elif flight["ticket_count"] > 0 and data["route_id"] != flight["route_id"]:
                error = "Нельзя менять маршрут после выпуска билетов на этот рейс."
            elif flight["ticket_count"] > 0 and data["aircraft_id"] != flight["aircraft_id"]:
                error = "Нельзя менять самолёт после выпуска билетов: места уже привязаны к текущему борту."
            else:
                try:
                    with get_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                SELECT 1
                                FROM aircraft
                                WHERE aircraft_id = %s
                                  AND in_service = TRUE
                                  AND EXISTS (
                                      SELECT 1 FROM seat s
                                      WHERE s.aircraft_id = aircraft.aircraft_id
                                  );
                            """, (data["aircraft_id"],))
                            if not cur.fetchone():
                                raise ValueError("Выбранный самолёт сейчас не находится в эксплуатации.")

                            cur.execute("""
                                UPDATE flight
                                SET
                                    route_id = %s,
                                    aircraft_id = %s,
                                    flight_number = %s,
                                    departure_time = %s,
                                    arrival_time = %s,
                                    status = %s
                                WHERE flight_id = %s;
                            """, (
                                data["route_id"],
                                data["aircraft_id"],
                                data["flight_number"],
                                data["departure_time"],
                                data["arrival_time"],
                                data["status"],
                                flight_id
                            ))

                    flash(f"Рейс {data['flight_number']} обновлён.")
                    return redirect(url_for("flights"))
                except ValueError as exc:
                    error = str(exc)
                except psycopg.errors.UniqueViolation:
                    error = "Рейс с таким номером и временем вылета уже существует."
                except psycopg.errors.ForeignKeyViolation:
                    error = "Выбранный маршрут или самолёт больше не существует."
                except psycopg.errors.CheckViolation:
                    error = "Проверьте время и статус рейса."

    routes, aircraft = _flight_form_options()
    return render_template(
        "flight_form.html",
        mode="edit",
        flight=flight,
        routes=routes,
        aircraft=aircraft,
        error=error
    )


@app.post("/admin/flights/<int:flight_id>/cancel")
def cancel_flight(flight_id):
    check_csrf()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT flight_number, status
                FROM flight
                WHERE flight_id = %s
                FOR UPDATE;
            """, (flight_id,))
            flight = cur.fetchone()

            if not flight:
                flash("Рейс не найден.")
                return redirect(url_for("flights"))

            if flight["status"] == "Cancelled":
                flash("Рейс уже отменён.")
                return redirect(url_for("flights"))

            if flight["status"] in ("Departed", "Arrived"):
                flash("Завершённый рейс нельзя отменить.")
                return redirect(url_for("flights"))

            cur.execute("""
                UPDATE flight
                SET status = 'Cancelled'
                WHERE flight_id = %s;
            """, (flight_id,))

            cur.execute("""
                UPDATE ticket
                SET status = 'Cancelled'
                WHERE flight_id = %s
                  AND status <> 'Cancelled';
            """, (flight_id,))

            cur.execute("""
                UPDATE booking b
                SET status = 'Cancelled'
                WHERE EXISTS (
                    SELECT 1
                    FROM ticket t
                    WHERE t.booking_id = b.booking_id
                      AND t.flight_id = %s
                )
                  AND b.status <> 'Cancelled';
            """, (flight_id,))

            cur.execute("""
                UPDATE payment p
                SET status = 'Refunded'
                WHERE p.status = 'Completed'
                  AND EXISTS (
                    SELECT 1
                    FROM ticket t
                    WHERE t.booking_id = p.booking_id
                      AND t.flight_id = %s
                );
            """, (flight_id,))

    flash(f"Рейс {flight['flight_number']} отменён. Связанные брони и билеты помечены как Cancelled.")
    return redirect(url_for("flights"))


# =========================================================

# PASSENGERS

# =========================================================



@app.route("/admin/passengers")
def passengers():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    p.passenger_id,
                    p.first_name,
                    p.last_name,
                    p.date_of_birth,
                    p.email,
                    p.phone,
                    p.passport_number,
                    p.loyalty_number,
                    p.created_at,
                    COUNT(DISTINCT b.booking_id) AS booking_count
                FROM passenger p
                LEFT JOIN booking b ON b.passenger_id = p.passenger_id
                GROUP BY
                    p.passenger_id,
                    p.first_name,
                    p.last_name,
                    p.date_of_birth,
                    p.email,
                    p.phone,
                    p.passport_number,
                    p.loyalty_number,
                    p.created_at
                ORDER BY p.passenger_id DESC;
            """)
            passenger_list = cur.fetchall()

    return render_template(
        "passengers.html",
        passengers=passenger_list
    )


# =========================================================

# ADD PASSENGER

# =========================================================



@app.route("/admin/passengers/add", methods=["GET", "POST"])

def add_passenger():



    error = None



    if request.method == "POST":

        check_csrf()



        first_name = request.form["first_name"].strip()

        last_name = request.form["last_name"].strip()

        date_of_birth = request.form["date_of_birth"]



        email = request.form.get("email", "").strip() or None

        phone = request.form.get("phone", "").strip() or None



        passport_number = request.form["passport_number"].strip()



        loyalty_number = (

            request.form.get("loyalty_number", "").strip()

            or None

        )



        try:



            with get_connection() as conn:

                with conn.cursor() as cur:



                    cur.execute("""

                        INSERT INTO passenger (

                            first_name,

                            last_name,

                            date_of_birth,

                            email,

                            phone,

                            passport_number,

                            loyalty_number

                        )



                        VALUES (

                            %s,

                            %s,

                            %s,

                            %s,

                            %s,

                            %s,

                            %s

                        );

                    """, (

                        first_name,

                        last_name,

                        date_of_birth,

                        email,

                        phone,

                        passport_number,

                        loyalty_number

                    ))



            return redirect(

                url_for("passengers")

            )



        except psycopg.errors.UniqueViolation:



            error = (

                "Passport number or loyalty number "

                "already exists."

            )



    return render_template(

        "add_passenger.html",

        error=error

    )





@app.post("/admin/passengers/<int:passenger_id>/delete")
def delete_passenger(passenger_id):
    check_csrf()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT first_name, last_name
                FROM passenger
                WHERE passenger_id = %s;
            """, (passenger_id,))
            passenger = cur.fetchone()

            if not passenger:
                flash("Пассажир уже удалён или не найден.")
                return redirect(url_for("passengers"))

            cur.execute("""
                SELECT COUNT(*) AS booking_count
                FROM booking
                WHERE passenger_id = %s;
            """, (passenger_id,))
            booking_count = cur.fetchone()["booking_count"]

            if booking_count > 0:
                flash(
                    "Нельзя удалить пассажира, пока у него есть бронирования. "
                    "Сначала удалите связанные брони."
                )
                return redirect(url_for("passengers"))

            cur.execute(
                "DELETE FROM passenger WHERE passenger_id = %s;",
                (passenger_id,)
            )

    flash(
        f"Пассажир {passenger['first_name']} {passenger['last_name']} удалён."
    )
    return redirect(url_for("passengers"))


# =========================================================

# BOOKINGS LIST

# =========================================================



@app.route("/admin/bookings")

def bookings():



    with get_connection() as conn:

        with conn.cursor() as cur:



            cur.execute("""

                SELECT

                    b.booking_id,

                    b.booking_reference,

                    b.booked_at,

                    b.status AS booking_status,



                    p.first_name,

                    p.last_name,



                    t.ticket_number,

                    t.price,

                    t.status AS ticket_status,



                    f.flight_number,



                    origin.iata_code AS origin,

                    destination.iata_code AS destination,



                    s.seat_number,

                    s.seat_class



                FROM booking b



                JOIN passenger p

                    ON b.passenger_id = p.passenger_id



                LEFT JOIN ticket t

                    ON b.booking_id = t.booking_id



                LEFT JOIN flight f

                    ON t.flight_id = f.flight_id



                LEFT JOIN route r

                    ON f.route_id = r.route_id



                LEFT JOIN airport origin

                    ON r.origin_airport_id = origin.airport_id



                LEFT JOIN airport destination

                    ON r.destination_airport_id = destination.airport_id



                LEFT JOIN seat s

                    ON t.seat_id = s.seat_id



                ORDER BY b.booking_id DESC;

            """)



            booking_list = cur.fetchall()



    return render_template(

        "bookings.html",

        bookings=booking_list

    )





@app.post("/admin/bookings/<int:booking_id>/delete")
def delete_booking(booking_id):
    check_csrf()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT booking_reference
                FROM booking
                WHERE booking_id = %s;
            """, (booking_id,))
            booking = cur.fetchone()

            if not booking:
                flash("Бронирование уже удалено или не найдено.")
                return redirect(url_for("bookings"))

            # payment and ticket have foreign keys to booking.
            cur.execute(
                "DELETE FROM payment WHERE booking_id = %s;",
                (booking_id,)
            )
            cur.execute(
                "DELETE FROM ticket WHERE booking_id = %s;",
                (booking_id,)
            )
            cur.execute(
                "DELETE FROM booking WHERE booking_id = %s;",
                (booking_id,)
            )

    flash(f"Бронирование {booking['booking_reference']} удалено.")
    return redirect(url_for("bookings"))


# =========================================================

# API: AVAILABLE SEATS FOR A FLIGHT

# =========================================================



@app.route("/api/flights/<int:flight_id>/seat-map")
def flight_seat_map(flight_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    f.flight_id,
                    f.flight_number,
                    f.departure_time,
                    f.status,
                    a.model,
                    a.registration_number
                FROM flight f
                JOIN aircraft a ON a.aircraft_id = f.aircraft_id
                WHERE f.flight_id = %s
                  AND f.status IN ('Scheduled', 'Boarding')
                  AND f.departure_time > CURRENT_TIMESTAMP;
            """, (flight_id,))
            flight = cur.fetchone()

            if not flight:
                return jsonify({"error": "Flight is not available"}), 404

            cur.execute("""
                SELECT
                    s.seat_id,
                    s.seat_number,
                    s.seat_class,
                    ROUND(
                        (12000 + r.distance_km * 8) *
                        CASE s.seat_class
                            WHEN 'Business' THEN 1.8
                            WHEN 'First' THEN 2.5
                            ELSE 1
                        END,
                        2
                    ) AS price,
                    EXISTS (
                        SELECT 1
                        FROM ticket t
                        WHERE t.flight_id = f.flight_id
                          AND t.seat_id = s.seat_id
                          AND t.status <> 'Cancelled'
                    ) AS occupied
                FROM flight f
                JOIN route r ON r.route_id = f.route_id
                JOIN seat s ON s.aircraft_id = f.aircraft_id
                WHERE f.flight_id = %s;
            """, (flight_id,))
            rows = cur.fetchall()

    def seat_key(row):
        match = re.match(r"^(\d+)([A-Za-z]+)$", str(row["seat_number"]))
        if not match:
            return (9999, str(row["seat_number"]))
        return (int(match.group(1)), match.group(2).upper())

    sorted_rows = sorted(rows, key=seat_key)
    seats = []
    for row in sorted_rows:
        match = re.match(r"^(\d+)([A-Za-z]+)$", str(row["seat_number"]))
        row_number = int(match.group(1)) if match else None
        column = match.group(2).upper() if match else str(row["seat_number"])
        seats.append({
            "seat_id": row["seat_id"],
            "seat_number": row["seat_number"],
            "seat_class": row["seat_class"],
            "price": float(row["price"]),
            "available": not bool(row["occupied"]),
            "row": row_number,
            "column": column
        })

    return jsonify({
        "flight": {
            "flight_number": flight["flight_number"],
            "model": flight["model"],
            "registration_number": flight["registration_number"]
        },
        "seats": seats
    })


@app.route("/api/flights/<int:flight_id>/seats")

def available_seats(flight_id):



    with get_connection() as conn:

        with conn.cursor() as cur:



            cur.execute("""

                SELECT

                    s.seat_id,

                    s.seat_number,

                    s.seat_class,



                    ROUND(

                        (

                            12000 + r.distance_km * 8

                        )

                        *

                        CASE

                            WHEN s.seat_class = 'Business'

                                THEN 1.8

                            WHEN s.seat_class = 'First'

                                THEN 2.5

                            ELSE 1

                        END,

                        2

                    ) AS price



                FROM flight f



                JOIN route r

                    ON f.route_id = r.route_id



                JOIN seat s

                    ON s.aircraft_id = f.aircraft_id



                WHERE f.flight_id = %s



                AND f.status IN (

                    'Scheduled',

                    'Boarding'

                )

                AND f.departure_time > CURRENT_TIMESTAMP



                AND NOT EXISTS (

                    SELECT 1

                    FROM ticket t

                    WHERE t.flight_id = f.flight_id

                    AND t.seat_id = s.seat_id
                    AND t.status <> 'Cancelled'

                )



                ORDER BY

                    s.seat_class,

                    s.seat_number;

            """, (flight_id,))



            rows = cur.fetchall()



    seats = []



    for row in rows:



        seats.append({

            "seat_id": row["seat_id"],

            "seat_number": row["seat_number"],

            "seat_class": row["seat_class"],

            "price": float(row["price"])

        })



    return jsonify({

        "seats": seats

    })



# =========================================================
# API: MINIMUM PRICES FOR TWO-MONTH CALENDAR
# =========================================================

@app.route("/api/calendar-prices")
def calendar_prices():
    origin_id = request.args.get("origin_id", type=int)
    destination_id = request.args.get("destination_id", type=int)
    month_raw = request.args.get("month", "").strip()

    if not origin_id or not destination_id or origin_id == destination_id:
        return jsonify({"prices": []})

    try:
        year_text, month_text = month_raw.split("-", 1)
        year = int(year_text)
        month = int(month_text)
        month_start = date(year, month, 1)
    except (ValueError, TypeError):
        return jsonify({"prices": []}), 400

    # The popup shows two months at once, so request exactly that range.
    if month_start.month == 11:
        range_end = date(month_start.year + 1, 1, 1)
    elif month_start.month == 12:
        range_end = date(month_start.year + 1, 2, 1)
    else:
        range_end = date(month_start.year, month_start.month + 2, 1)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    f.departure_time::date AS flight_date,
                    MIN(
                        ROUND(
                            (12000 + r.distance_km * 8) *
                            CASE s.seat_class
                                WHEN 'Business' THEN 1.8
                                WHEN 'First' THEN 2.5
                                ELSE 1
                            END,
                            2
                        )
                    ) AS min_price
                FROM flight f
                JOIN route r
                    ON r.route_id = f.route_id
                JOIN seat s
                    ON s.aircraft_id = f.aircraft_id
                WHERE r.origin_airport_id = %s
                  AND r.destination_airport_id = %s
                  AND f.departure_time >= %s
                  AND f.departure_time < %s
                  AND f.departure_time > CURRENT_TIMESTAMP
                  AND f.status IN ('Scheduled', 'Boarding')
                  AND NOT EXISTS (
                      SELECT 1
                      FROM ticket t
                      WHERE t.flight_id = f.flight_id
                        AND t.seat_id = s.seat_id
                        AND t.status <> 'Cancelled'
                  )
                GROUP BY f.departure_time::date
                ORDER BY flight_date;
            """, (origin_id, destination_id, month_start, range_end))

            rows = cur.fetchall()

    prices = []
    for row in rows:
        prices.append({
            "date": row["flight_date"].isoformat(),
            "price": float(row["min_price"])
        })

    return jsonify({"prices": prices})



# =========================================================

# CREATE BOOKING

# =========================================================



@app.route("/admin/bookings/new", methods=["GET", "POST"])

def create_booking():



    error = None



    # Если пользователь нажал Book на странице Flights,

    # сюда придёт flight_id.

    preselected_flight_id = request.args.get(

        "flight_id",

        type=int

    )



    # -----------------------------------------------------

    # CREATE BOOKING + TICKET

    # -----------------------------------------------------



    if request.method == "POST":

        check_csrf()



        passenger_id = request.form.get(

            "passenger_id",

            type=int

        )



        flight_id = request.form.get(

            "flight_id",

            type=int

        )



        seat_id = request.form.get(

            "seat_id",

            type=int

        )



        if not passenger_id or not flight_id or not seat_id:



            error = (

                "Passenger, flight and seat "

                "must all be selected."

            )



        else:



            try:



                with get_connection() as conn:

                    with conn.cursor() as cur:



                        # ----------------------------------

                        # Проверяем выбранный рейс и место

                        # ----------------------------------



                        cur.execute("""

                            SELECT

                                f.flight_id,

                                f.flight_number,



                                s.seat_id,

                                s.seat_number,

                                s.seat_class,



                                r.distance_km,



                                ROUND(

                                    (

                                        12000 + r.distance_km * 8

                                    )

                                    *

                                    CASE

                                        WHEN s.seat_class = 'Business'

                                            THEN 1.8

                                        WHEN s.seat_class = 'First'

                                            THEN 2.5

                                        ELSE 1

                                    END,

                                    2

                                ) AS price



                            FROM flight f



                            JOIN route r

                                ON f.route_id = r.route_id



                            JOIN seat s

                                ON s.aircraft_id = f.aircraft_id



                            WHERE f.flight_id = %s

                            AND s.seat_id = %s



                            AND f.status IN (

                                'Scheduled',

                                'Boarding'

                            )

                            AND f.departure_time > CURRENT_TIMESTAMP



                            AND NOT EXISTS (

                                SELECT 1

                                FROM ticket existing_ticket

                                WHERE existing_ticket.flight_id = f.flight_id

                                AND existing_ticket.seat_id = s.seat_id
                                AND existing_ticket.status <> 'Cancelled'

                            );

                        """, (

                            flight_id,

                            seat_id

                        ))



                        selected = cur.fetchone()



                        if selected is None:



                            raise ValueError(

                                "The selected seat is no longer available."

                            )



                        price = selected["price"]



                        # ----------------------------------

                        # Generate unique references

                        # ----------------------------------



                        booking_reference = (

                            "BK" +

                            uuid.uuid4()

                            .hex[:8]

                            .upper()

                        )



                        ticket_number = (

                            "TKT" +

                            uuid.uuid4()

                            .hex[:10]

                            .upper()

                        )



                        # ----------------------------------

                        # INSERT BOOKING

                        # ----------------------------------



                        cur.execute("""

                            INSERT INTO booking (

                                passenger_id,

                                booking_reference,

                                status

                            )



                            VALUES (

                                %s,

                                %s,

                                'Confirmed'

                            )



                            RETURNING booking_id;

                        """, (

                            passenger_id,

                            booking_reference

                        ))



                        new_booking = cur.fetchone()



                        booking_id = (

                            new_booking["booking_id"]

                        )



                        # ----------------------------------

                        # INSERT TICKET

                        # ----------------------------------



                        cur.execute("""

                            INSERT INTO ticket (

                                booking_id,

                                flight_id,

                                seat_id,

                                ticket_number,

                                price,

                                status

                            )



                            VALUES (

                                %s,

                                %s,

                                %s,

                                %s,

                                %s,

                                'Issued'

                            );

                        """, (

                            booking_id,

                            flight_id,

                            seat_id,

                            ticket_number,

                            price

                        ))



                flash(

                    "Booking created successfully."

                )



                return redirect(

                    url_for("bookings")

                )



            except ValueError as e:



                error = str(e)



            except psycopg.errors.UniqueViolation:



                error = (

                    "This seat was already booked. "

                    "Please choose another seat."

                )





    # -----------------------------------------------------

    # DATA FOR FORM

    # -----------------------------------------------------



    with get_connection() as conn:

        with conn.cursor() as cur:



            # Passengers

            cur.execute("""

                SELECT

                    passenger_id,

                    first_name,

                    last_name,

                    passport_number



                FROM passenger



                ORDER BY

                    first_name,

                    last_name;

            """)



            passenger_list = cur.fetchall()





            # Flights available for booking

            cur.execute("""

                SELECT

                    f.flight_id,

                    f.flight_number,

                    f.departure_time,



                    origin.iata_code AS origin,

                    destination.iata_code AS destination



                FROM flight f



                JOIN route r

                    ON f.route_id = r.route_id



                JOIN airport origin

                    ON r.origin_airport_id = origin.airport_id



                JOIN airport destination

                    ON r.destination_airport_id = destination.airport_id



                WHERE f.status IN (

                    'Scheduled',

                    'Boarding'

                )

                AND f.departure_time > CURRENT_TIMESTAMP



                ORDER BY f.departure_time;

            """)



            flight_list = cur.fetchall()



    return render_template(

        "create_booking.html",

        passengers=passenger_list,

        flights=flight_list,

        error=error,

        preselected_flight_id=preselected_flight_id

    )





# =========================================================

# START FLASK

# =========================================================



if __name__ == "__main__":

    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
