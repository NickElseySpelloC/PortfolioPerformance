"""Manages input price data files and provides methods to read and merge them and return a price for a given date."""

import csv
from datetime import date
from pathlib import Path

from sc_utility import DateHelper


class PriceDataManager:
    def __init__(self, config, logger):
        """Initializes the PriceDataManager with configuration and logger."""
        self.config = config
        self.logger = logger
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
            if DateHelper.get_file_date(file_path) < DateHelper.today_add_days(-max_age) and max_age > 0:
                self.logger.log_fatal_error(f"Price data file {file_path} is older than {max_age} days.")
                continue
            data = self._read_csv(file_path)

            for entry in data:
                # Convert the Date column to a date object
                if "Date" in entry:
                    entry["Date"] = DateHelper.parse_date(entry["Date"], "%Y-%m-%d")
                    if entry["Date"] is None:
                        self.logger.log_message(f"Invalid date value for {entry.get('Symbol')} on {entry.get('Date')}", "error")

                        # Remove this entry from the data if the date is invalid
                        data.remove(entry)
                        continue
                # Convert the Price column to a float
                if "Price" in entry:
                    try:
                        entry["Price"] = float(entry["Price"])
                    except (TypeError, ValueError):
                        self.logger.log_message(f"Invalid price value for {entry.get('Symbol')} on {entry.get('Date')}", "error")
                        # Remove this entry from the data if the date is invalid
                        data.remove(entry)
                        continue
            if data is None:
                self.logger.log_fatal_error(f"Failed to read price data from {file_path}")
            else:
                self.price_data.extend(data)
                self.logger.log_message(f"Imported price data from {file_path}", "summary")

        # Sort the price data by descending date dand symbol
        self.price_data.sort(key=lambda x: (x.get("Date", ""), x.get("Symbol", "")), reverse=True)


    def _read_csv(self, file_path):
        """Reads a CSV file and returns its content as a list of dictionaries."""
        data = []
        if file_path.exists():
            try:
                with file_path.open(newline="", encoding="utf-8") as csvfile:
                    reader = csv.DictReader(csvfile)
                    data = list(reader)
            except (FileNotFoundError, csv.Error, OSError) as e:
                self.logger.log_message(f"Error reading CSV file {file_path}: {e}", "error")
            else:
                return data

        return None

    def get_price_on_date(self, symbol: str, date: date) -> tuple[float | None, str | None]:
        """Returns the price for a given date from the imported price data."""
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
