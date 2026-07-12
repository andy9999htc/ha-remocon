"""Pytest configuration and fixtures."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Create a mock hierarchy for all homeassistant modules
ha_mock = MagicMock()
sys.modules['homeassistant'] = ha_mock
sys.modules['homeassistant.config_entries'] = MagicMock()
sys.modules['homeassistant.const'] = MagicMock()
sys.modules['homeassistant.core'] = MagicMock()
sys.modules['homeassistant.exceptions'] = MagicMock()
sys.modules['homeassistant.helpers'] = MagicMock()
sys.modules['homeassistant.helpers.service'] = MagicMock()
sys.modules['homeassistant.helpers.config_validation'] = MagicMock()
sys.modules['homeassistant.helpers.update_coordinator'] = MagicMock()
sys.modules['homeassistant.helpers.entity_platform'] = MagicMock()
sys.modules['homeassistant.components'] = MagicMock()
sys.modules['homeassistant.components.climate'] = MagicMock()
sys.modules['homeassistant.components.sensor'] = MagicMock()
sys.modules['homeassistant.components.binary_sensor'] = MagicMock()
sys.modules['homeassistant.components.number'] = MagicMock()
sys.modules['homeassistant.components.select'] = MagicMock()

# Add the custom_components directory to the path so imports work
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))
