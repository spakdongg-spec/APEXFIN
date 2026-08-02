"""Yahoo Finance chart collector -- the optional, advanced path.

Terms of use, stated plainly rather than buried: Yahoo Finance publishes no
commercial data API licence and its terms limit use to personal,
non-commercial purposes. Data obtained through this collector is for personal
research and education. You are responsible for complying with Yahoo's terms.
This project distributes no data and ships no credentials.

Deliberately absent, and not to be re-added (ADR-009 / ARCHITECTURE 8.2):
  - user-agent rotation or a pool of browser-looking identifiers
  - a second host or any fallback chain
  - retry-around behaviour on 429 or 403

One host, one honest identifying user agent, at least 1.5 seconds between
requests, and a full stop the moment the upstream says no.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

import httpx

from apexfin import __version__
from apexfin.core.enums import Frequency
from apexfin.core.errors import CollectorError, SourceBlockedError
from apexfin.core.models import FetchWindow, RawRecord, SourceCapabilities
from apexfin.core.registry import register_source
from apexfin.sources.base import BaseCollector

MIN_REQUEST_INTERVAL_S = 1.5
REPO_URL = "https://github.com/apexfin/apexfin"


@register_source("yahoo")
class YahooCollector(BaseCollector):
    """Daily closes from the public Yahoo chart endpoint."""

    HOST = "https://query1.finance.yahoo.com"
    PATH = "/v8/finance/chart/{symbol}"
    USER_AGENT = f"apexfin/{__version__} (+{REPO_URL})"

    def __init__(
        self,
        symbols: tuple[str, ...] = ("SPY",),
        domain: str = "equity",
        min_request_interval_s: float = MIN_REQUEST_INTERVAL_S,
        client: httpx.Client | None = None,
        timeout_s: float = 15.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._symbols = symbols
        self._domain = domain
        # Configurable upwards only. A politeness floor that callers can lower
        # is not a floor.
        self._interval = max(MIN_REQUEST_INTERVAL_S, float(min_request_interval_s))
        self._client = client
        self._timeout_s = timeout_s

    def capabilities(self) -> SourceCapabilities:
        return SourceCapabilities(
            source_name="yahoo",
            domain=self._domain,
            symbols=self._symbols,
            frequency=Frequency.DAILY,
            requires_credentials=False,
            supports_full_refresh=True,
            min_request_interval_s=self._interval,
        )

    def _http(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(
            timeout=self._timeout_s,
            headers={"User-Agent": self.USER_AGENT, "Accept": "application/json"},
        )

    def _fetch_raw(self, window: FetchWindow) -> Iterable[RawRecord]:
        client = self._http()
        owns_client = self._client is None
        records: list[RawRecord] = []
        try:
            for symbol in self._symbols:
                records.extend(self._fetch_symbol(client, symbol, window))
        finally:
            if owns_client:
                client.close()
        return records

    def _fetch_symbol(
        self, client: httpx.Client, symbol: str, window: FetchWindow
    ) -> list[RawRecord]:
        period1 = int(datetime.combine(window.start, datetime.min.time(), tzinfo=UTC).timestamp())
        period2 = int(datetime.combine(window.end, datetime.max.time(), tzinfo=UTC).timestamp())
        url = self.HOST + self.PATH.format(symbol=symbol)
        params: dict[str, str | int] = {
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "div,split",
        }

        self.before_request()
        try:
            response = client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise CollectorError(f"yahoo: transport failure for {symbol}: {exc}") from exc

        if response.status_code in (403, 429):
            raise SourceBlockedError(
                f"yahoo: upstream returned HTTP {response.status_code} for {symbol}. "
                "Stopping this source for the run. No retry, no host switch, no header "
                "rotation -- see ADR-009."
            )
        if response.status_code >= 500:
            raise CollectorError(f"yahoo: upstream HTTP {response.status_code} for {symbol}")
        if response.status_code != 200:
            raise CollectorError(f"yahoo: unexpected HTTP {response.status_code} for {symbol}")

        try:
            body = response.json()
        except ValueError as exc:
            raise CollectorError(f"yahoo: response for {symbol} is not JSON: {exc}") from exc
        return self._parse(symbol, body, url)

    def _parse(self, symbol: str, body: dict[str, Any], url: str) -> list[RawRecord]:
        chart = body.get("chart") or {}
        if chart.get("error"):
            raise CollectorError(f"yahoo: chart error for {symbol}: {chart['error']}")
        results = chart.get("result") or []
        if not results:
            raise CollectorError(f"yahoo: chart payload for {symbol} carries no result block")

        block = results[0]
        stamps = block.get("timestamp") or []
        quote_list = (block.get("indicators") or {}).get("quote") or [{}]
        quote = quote_list[0]
        closes = quote.get("close") or []
        volumes = quote.get("volume") or []

        out: list[RawRecord] = []
        for index, stamp in enumerate(stamps):
            close = closes[index] if index < len(closes) else None
            if close is None:
                continue
            volume = volumes[index] if index < len(volumes) else None
            out.append(
                RawRecord(
                    source_name="yahoo",
                    domain=self._domain,
                    symbol=symbol,
                    event_time=datetime.fromtimestamp(int(stamp), tz=UTC),
                    payload={"close": float(close), "volume": volume, "interval": "1d"},
                    source_url=url,
                )
            )
        return out
