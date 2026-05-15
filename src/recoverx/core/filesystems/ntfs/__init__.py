"""NTFS filesystem analysis and recovery for RecoverX.

Provides boot sector parsing, MFT record walking, attribute parsing,
data run resolution, resident and non-resident file recovery,
runlist execution engine, sparse support, USN journal parsing,
and $LogFile analysis.
"""

from __future__ import annotations

from recoverx.core.forensics import register_forensic_source

from .logfile.parser import LogFileParser
from .usn.parser import USNParser

register_forensic_source("usn", USNParser, "USN Journal Parser")
register_forensic_source("logfile", LogFileParser, "$LogFile Transaction Parser")
