"""Tests for core module credentials.

The core module has an empty CREDENTIAL_TYPES dict as it provides
base nodes that don't require credentials.
"""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.core.credentials import CREDENTIAL_TYPES


# ##################################################################
# test CREDENTIAL_TYPES is empty
def test_credential_types_is_empty_dict():
    assert CREDENTIAL_TYPES == {}


def test_credential_types_is_dict():
    assert isinstance(CREDENTIAL_TYPES, dict)
