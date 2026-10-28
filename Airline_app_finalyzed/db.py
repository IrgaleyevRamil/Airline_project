import psycopg
from psycopg.rows import dict_row


DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "airline_booking_system",
    "user": "postgres",
    "password": "1234"
}


def get_connection():
    return psycopg.connect(
        **DB_CONFIG,
        row_factory=dict_row
    )
