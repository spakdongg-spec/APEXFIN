"""Presentation layer (L5).

Turns persisted run state into a DataPack the dashboard template consumes.
Allowed to import `core` and `storage` only: reporting must never be able to
change what it reports on.
"""

from apexfin.reporting.datapack import build_datapack, build_datapack_dict
from apexfin.reporting.models import DataPack

__all__ = ["DataPack", "build_datapack", "build_datapack_dict"]
