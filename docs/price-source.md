# Price source

Flight prices come from the **Travelpayouts / Aviasales Data API**.

## Why this API

| Option | Status (Oct 2026) |
|---|---|
| Amadeus Self-Service | Shut down on 17 Jul 2026 (enterprise contracts only) |
| **Travelpayouts / Aviasales Data API** | **Free with an account token, no approval needed** |

Aviasales is a metasearch engine: prices come from many airlines and agencies, and each result includes a booking link.

## What the data is (and is not)

- **Cached, not live.** Prices found by Aviasales users in recent searches, kept for **2–7 days**. The price may have changed when the link is opened.
- **Per adult.** Multiply by the number of passengers for the trip total.
- **Not exhaustive.** Popular routes and near dates are well covered; rare routes and far dates are sparse.
- **Links are relative.** Prepend `https://www.aviasales.com` to the `link` field.
- **Stops, not layovers.** The response gives the number of stops per leg (`transfers`, `return_transfers`) but not layover durations or whether a 1-stop trip is two separate tickets. The watcher therefore filters by number of stops only, and alerts cannot say where the stop is; the booking page shows it.
- **Times.** `departure_at` and `return_at` include the departure time, in the local time of each departure airport (with its UTC offset).
- **Flight time.** `duration_to` and `duration_back` are the flight time of each leg in minutes, layovers included (`duration` is both legs). The watcher uses it as a proxy for distance to choose the allowed trip length.
- **City names.** The free data file `https://api.travelpayouts.com/data/{language}/cities.json` (no token) maps IATA city codes to names. It is downloaded at most every 30 days and cached in the history database. Some names are official rather than everyday (`BIO` is "Ciudad de Bilbao" in Spanish), so `search.city_names` in the instance config can override them.
- **City countries.** The English `cities.json` also gives each city's `country_code`, used by `search.direct_only_countries` (e.g. no stops within Spain). Cities missing from the file are kept.
- **Airline names.** `https://api.travelpayouts.com/data/en/airlines.json` maps airline codes (`V7`) to names (`Volotea`), cached the same way. The `airline` field of a fare is a single carrier, even when the return is flown by another airline.

## Account and token

1. Sign up at [travelpayouts.com](https://www.travelpayouts.com/). The onboarding asks for a channel; the Telegram bot link is accepted (GitHub links are not).
2. Copy the token from **app.travelpayouts.com → Profile → API token**. "Regenerate token" invalidates the previous one immediately.
3. Store it without echoing it:

```bash
read -rsp "Travelpayouts token: " T && printf 'TRAVELPAYOUTS_API_TOKEN=%s\n' "$T" >> .env && unset T
```

## Example request

The token is sent as a header, so it never appears in URLs or logs:

```bash
source .env
curl -s -H "X-Access-Token: ${TRAVELPAYOUTS_API_TOKEN}" \
  "https://api.travelpayouts.com/aviasales/v3/prices_for_dates?origin=BIO&departure_at=2026-12&currency=eur&market=es&one_way=false&sorting=price&limit=1000"
```

Relevant response fields:

| Field | Example | Meaning |
|---|---|---|
| `origin_airport` / `destination_airport` | `BIO` / `MXP` | Airports (IATA) |
| `destination` | `MIL` | City code (groups all airports of a city) |
| `departure_at` / `return_at` | `2026-10-29T16:40:00+01:00` | Outbound and return departure times |
| `price` | `26` | Round-trip price per adult, in `currency` |
| `transfers` / `return_transfers` | `0` | Stops on each leg |
| `airline` / `flight_number` | `W4` / `6412` | Marketing carrier and flight |
| `gate` | `Farera` | Agency selling the fare |
| `link` | `/search/BIO2910MIL1911?...` | Relative booking link |

## How the watcher queries it

- One request per **departure month** covered by the instance's deal windows (7–180 days ahead → about 6 requests per run), with `destination` omitted ("anywhere").
- Every fare is then filtered locally: max stops on either leg, deal window by days ahead, de-duplication.
- Querying popular destinations individually, to get more results for far months, is planned once there is price history to show where it helps.

## Rate limits

`/v3/prices_for_dates` allows **600 requests per minute**; exceeding a limit returns HTTP `429`. The watcher makes a few requests every 6 hours, far below the limit.

## Coverage from Bilbao

Snapshot taken on 2026-10-25 with one request per departure month (`origin=BIO`, round trip, `limit=1000`):

| Departure month | Results | Destinations | Direct | Cheapest (pp) |
|---|---|---|---|---|
| 2026-11 | 108 | 45 | 35 | €30 |
| 2026-12 | 115 | 52 | 18 | €33 |
| 2027-01 | 36 | 21 | 6 | €59 |
| 2027-02 | 9 | 7 | 2 | €35 |
| 2027-03 | 14 | 11 | 4 | €73 |
| 2027-04 | 22 | 11 | 3 | €62 |

**Implications for Phase 1**

- Also query **per destination** for popular routes to get more results for far months.
- **Store every price on every run**, so the "usual price" baseline improves over time.
- Expect the per-person price rules, not the percentage-drop rules, to trigger most alerts at first.
- Long-haul destinations in the results usually have 2+ stops and are dropped by `max_stops: 1`.

## References

- [Aviasales Data API](https://support.travelpayouts.com/hc/en-us/articles/203956163)
- [Access requirements](https://support.travelpayouts.com/hc/en-us/articles/203956083-Requirements-for-Aviasales-data-API-access)
- [API rate limits](https://support.travelpayouts.com/hc/en-us/articles/4402565416594)
