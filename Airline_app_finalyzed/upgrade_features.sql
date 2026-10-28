-- =========================================================
-- Airline Booking System — Feature Pack V2 database upgrade
-- Run ONCE in pgAdmin Query Tool on airline_booking_system.
--
-- Why this is needed:
-- a cancelled ticket should stay in the database for history,
-- but its seat must be allowed to be sold again.
-- =========================================================

BEGIN;

-- Old rule blocked a seat forever, even when ticket.status = 'Cancelled'.
ALTER TABLE public.ticket
    DROP CONSTRAINT IF EXISTS uq_flight_seat;

-- Only an ACTIVE (non-cancelled) ticket reserves a seat.
CREATE UNIQUE INDEX IF NOT EXISTS uq_flight_seat_active
    ON public.ticket (flight_id, seat_id)
    WHERE status <> 'Cancelled';

COMMIT;
