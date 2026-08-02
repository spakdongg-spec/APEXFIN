"""Opinion accounting (L3).

Records every stance the system took and, later, grades it. Kept in its own
package rather than folded into `decision/` because writing an opinion and
scoring an opinion are different jobs with different failure modes: the first
must never lose a row, the second must never invent an outcome.

Depends on `core` only -- it talks to storage through the narrow ledger ports.
"""

from apexfin.accounting.ledger import write_opinion_ledger
from apexfin.accounting.settlement import SettlementSummary, settle_due_entries

__all__ = ["SettlementSummary", "settle_due_entries", "write_opinion_ledger"]
