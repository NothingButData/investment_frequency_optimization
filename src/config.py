"""Configuration loader and validator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


@dataclass
class ClientConfig:
    monthly_amount: float
    investment_day: int
    ticker: str
    start_date: str
    end_date: str
    transaction_cost: float


@dataclass
class AnalysisConfig:
    bootstrap_iterations: int
    random_simulations: int
    confidence_level: float


@dataclass
class Config:
    client: ClientConfig
    analysis: AnalysisConfig


def load_config(path: Path | str | None = None) -> Config:
    """Load and validate configuration from a YAML file."""
    path = Path(path) if path else DEFAULT_CONFIG_PATH

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    client_raw = raw.get("client", {})
    analysis_raw = raw.get("analysis", {})

    client = ClientConfig(
        monthly_amount=float(client_raw["monthly_amount"]),
        investment_day=int(client_raw["investment_day"]),
        ticker=str(client_raw["ticker"]).upper(),
        start_date=str(client_raw["start_date"]),
        end_date=str(client_raw["end_date"]),
        transaction_cost=float(client_raw.get("transaction_cost", 0.0)),
    )

    analysis = AnalysisConfig(
        bootstrap_iterations=int(analysis_raw.get("bootstrap_iterations", 10000)),
        random_simulations=int(analysis_raw.get("random_simulations", 1000)),
        confidence_level=float(analysis_raw.get("confidence_level", 0.95)),
    )

    _validate(client, analysis)

    return Config(client=client, analysis=analysis)


def _validate(client: ClientConfig, analysis: AnalysisConfig) -> None:
    """Raise ValueError on bad config values."""
    if client.monthly_amount <= 0:
        raise ValueError(f"monthly_amount must be > 0, got {client.monthly_amount}")

    if not 1 <= client.investment_day <= 28:
        raise ValueError(
            f"investment_day must be 1–28, got {client.investment_day}"
        )

    start = datetime.strptime(client.start_date, "%Y-%m-%d").date()
    end = datetime.strptime(client.end_date, "%Y-%m-%d").date()

    if end <= start:
        raise ValueError(f"end_date ({end}) must be after start_date ({start})")

    if (end - start).days < 365:
        raise ValueError("Date range must span at least 1 year")

    if client.transaction_cost < 0:
        raise ValueError(
            f"transaction_cost must be >= 0, got {client.transaction_cost}"
        )

    if not 0 < analysis.confidence_level < 1:
        raise ValueError(
            f"confidence_level must be between 0 and 1, "
            f"got {analysis.confidence_level}"
        )
