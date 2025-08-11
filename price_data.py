"""Manages input price data files and provides methods to read and merge them and return a price for a given date."""

import datetime as dt
from pathlib import Path

from sc_utility import CSVReader, DateHelper


class PriceDataManager:
    def __init__(self, config, logger, header_config):
        """
        Initializes the PriceDataManager with configuration and logger.

        Args:
            config: Configuration object containing file paths and settings.
            logger: Logger object for logging messages and errors.
            header_config (list[dict]): Configuration for the CSV header, including field names and types.
        """
        self.config = config
        self.logger = logger
        self.csv_header_config = header_config
        self.price_data = []

        # Import price data from configured files
        self._import_price_data()

    def _import_price_data(self):
        """Imports price data from configured CSV files."""
        file_list = self.config.get("Files", "PriceDataFiles")
        for file_config in file_list:
            file_path = Path(file_config["DataFile"])
            max_age = file_config.get("MaxAge", 5)

            # Check if the file exists and is not too old
            if not file_path.exists():
                self.logger.log_fatal_error(f"Price data file {file_path} does not exist.")
                continue

            # get the file's last modified date as a date object
            if DateHelper.get_file_date(file_path) < DateHelper.today_add_days(-max_age) and max_age > 0:  # type: ignore[call-arg]
                self.logger.log_fatal_error(f"Price data file {file_path} is older than {max_age} days.")
                continue
            data = self._read_csv(file_path)

            if data is None:
                continue
            self.price_data.extend(data)
            self.logger.log_message(f"Imported price data from {file_path}", "summary")

        # Sort the price data by descending date dand symbol
        self.price_data.sort(key=lambda x: (x.get("Date", ""), x.get("Symbol", "")), reverse=True)

    def _read_csv(self, file_path) -> list[dict] | None:
        """
        Reads a CSV file and returns its content as a list of dictionaries.

        Args:
            file_path (Path): The path to the CSV file to read.

        Returns:
            data (list[dict]): A list of dictionaries representing the rows in the CSV file.
        """
        # Create an instance of the CSVReader class and write the new file
        try:
            csv_reader = CSVReader(file_path, self.csv_header_config)
            data = csv_reader.read_csv()
        except (ImportError, TypeError, ValueError, RuntimeError) as e:
            self.logger.log_fatal_error(f"Failed to reader CSV price file {file_path}: {e}")

        return data

    def get_price_on_date(self, symbol: str, date: dt.date) -> tuple[float | None, str | None]:
        """
        Returns the price for a given date from the imported price data.

        Args:
            symbol (str): The symbol for which to get the price.
            date (date): The date for which to get the price.

        Returns:
            tuple: A tuple containing the price (float) and currency (str) if available, otherwise None.
        """
        if symbol.lower() == "cash":
            return 1.0, None  # Cash is always valued at 1.0

        for entry in self.price_data:
            if entry.get("Symbol") == symbol and entry.get("Date") <= date:
                try:
                    return entry.get("Price"), entry.get("Currency")
                except (TypeError, ValueError):
                    self.logger.log_message(f"Invalid price value for {symbol} on {entry.get('Date')}", "error")
                    return None, None
        self.logger.log_message(f"No price found for symbol [{symbol}] effective date {date}", "warning")
        return None, None

    def get_symbol_name(self, symbol: str) -> str:
        """Returns the name of the symbol if available in the price data."""
        for entry in self.price_data:
            if entry.get("Symbol") == symbol:
                return entry.get("Name", symbol)

        return "Unknown"
