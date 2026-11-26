"""ETL subpackage providing dataset generation and Iragi data quality auditing.

Example:
    Generate synthetic datasets from Python::

        >>> from pathlib import Path
        >>> from scripts.etl.generate_data import DatasetConfig, generate_all_datasets
        >>> cfg = DatasetConfig(output_dir=Path("data/raw"), deliveries_count=1000)
"""
