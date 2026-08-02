"""BaseCollector: the parts a third party must not be able to get wrong.

Subclasses implement `_fetch_raw` and nothing else. The base class owns:

  - politeness delay from `capabilities().min_request_interval_s`
  - retry with exponential backoff and jitter, for transient transport faults
    only (`CollectorError`)
  - empty-result guard: an empty iterable is a failure, never a silent no-op
  - per-source isolation: nothing raised here aborts the whole run

Access control is not a transient fault. HTTP 429 and 403 raise
`SourceBlockedError`, which is deliberately outside the retry set: retrying,
backing off and trying again, or switching host would all be ways of working
around a refusal. This project does not do that (ARCHITECTURE 8.2 C4,
ADR-009). If you are adding a source and find yourself wanting to put 429 into
the retry set, that is the line.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable

from tenacity import (
    RetryError,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from apexfin.core.errors import CollectorError, EmptyResultError, SourceBlockedError
from apexfin.core.models import CollectResult, FetchWindow, RawRecord, SourceCapabilities

MAX_ATTEMPTS = 3


class BaseCollector(ABC):
    """Fetch raw records from one upstream source."""

    def __init__(
        self,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._sleep = sleeper
        self._monotonic = monotonic
        self._last_request_at: float | None = None
        self.requests_made = 0

    @abstractmethod
    def capabilities(self) -> SourceCapabilities: ...

    @abstractmethod
    def _fetch_raw(self, window: FetchWindow) -> Iterable[RawRecord]:
        """Fetch and yield RawRecord. Raise on transport or parse failure.

        Must not swallow errors and return an empty iterable: the base class
        cannot tell 'genuinely no data' from 'silently broken' and therefore
        treats empty as failure.
        """

    def before_request(self) -> None:
        """Politeness gate. Subclasses call this immediately before each call."""
        interval = self.capabilities().min_request_interval_s
        if interval > 0 and self._last_request_at is not None:
            elapsed = self._monotonic() - self._last_request_at
            remaining = interval - elapsed
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_at = self._monotonic()
        self.requests_made += 1

    def fetch(self, window: FetchWindow) -> CollectResult:
        """Run the collector. Never raises; failures come back in the result."""
        started = self._monotonic()
        self.requests_made = 0
        try:
            records = self._fetch_with_retry(window)
        except SourceBlockedError as exc:
            return self._result(
                records=(), ok=False, status="blocked", error=str(exc), started=started
            )
        except (CollectorError, EmptyResultError) as exc:
            return self._result(
                records=(), ok=False, status="failed", error=str(exc), started=started
            )
        except Exception as exc:  # noqa: BLE001 - wrapped, never swallowed
            wrapped = CollectorError(f"{type(exc).__name__}: {exc}")
            return self._result(
                records=(), ok=False, status="failed", error=str(wrapped), started=started
            )
        return self._result(records=records, ok=True, status="ok", error=None, started=started)

    def _fetch_with_retry(self, window: FetchWindow) -> tuple[RawRecord, ...]:
        try:
            for attempt in Retrying(
                stop=stop_after_attempt(MAX_ATTEMPTS),
                wait=wait_exponential_jitter(initial=0.5, max=8.0),
                retry=retry_if_exception_type(CollectorError),
                sleep=self._sleep,
                reraise=True,
            ):
                with attempt:
                    records = tuple(self._fetch_raw(window))
        except RetryError as exc:  # pragma: no cover - reraise=True makes this rare
            raise CollectorError(str(exc)) from exc
        if not records:
            raise EmptyResultError(
                f"{self.capabilities().source_name}: returned 0 records for "
                f"{window.start.isoformat()}..{window.end.isoformat()}. "
                "An empty result is treated as failure, not as 'no new data'."
            )
        return records

    def _result(
        self,
        records: tuple[RawRecord, ...],
        ok: bool,
        status: str,
        error: str | None,
        started: float,
    ) -> CollectResult:
        return CollectResult(
            source_name=self.capabilities().source_name,
            records=records,
            ok=ok,
            status=status,  # type: ignore[arg-type]
            error=error,
            requests_made=self.requests_made,
            duration_s=round(self._monotonic() - started, 4),
        )
