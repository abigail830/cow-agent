"""CLI smoke test for primary and utility models."""

import asyncio
import sys
from pathlib import Path

# Ensure backend root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.platform.model_registry import ModelProviderRegistry
from app.platform.utility_models import UtilityModelRegistry


async def main() -> None:
    settings = get_settings()
    print(f"Primary deployment: {settings.azure_openai_deployment}")
    print(f"Utility deployment: {settings.utility_deployment()}")

    primary = await ModelProviderRegistry().smoke_test_primary()
    print(f"Primary response: {primary!r}")

    utility = await UtilityModelRegistry().smoke_test()
    print(f"Utility response: {utility!r}")


if __name__ == "__main__":
    asyncio.run(main())
