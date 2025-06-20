"""Manages the import and processing of portfolio data."""

import csv
import operator
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import cloudinary
import cloudinary.uploader
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd
from dotenv import load_dotenv

# import jinja2
from jinja2 import Environment, FileSystemLoader, TemplateError
from sc_utility import DateHelper, ExcelReader


def currency_thousands(x, _):
    """
    Formats a number as a currency string with thousands separator.

    Used by matplotlib to format y-axis labels.

    Args:
        x (float): The number to format.
        _: Unused parameter, required by matplotlib's FuncFormatter.

    Returns:
        str: The formatted currency string.
    """
    return f"${x / 1000:,.0f}k"


class PortfolioManager:
    """Manages the portfolio valuation and reporting for stock holdings."""

    def __init__(self, config, logger, price_data):
        """
        Initializes the PortfolioManager with configuration and logger.

        Args:
            config: An instance of the SCConfigManager class containing configuration settings.
            logger: An instance of the SCLogger class for logging messages.
            price_data: An instance of the PriceDataManager class with stock prices loaded.
        """
        self.config = config
        self.logger = logger
        self.price_data = price_data    # An instance of the PriceDataManager class with stock prices loaded
        self.report_name = self.config.get("Portfolio", "ReportName", default="Portfolio Performance Report")
        self.report_type = self.config.get("Portfolio", "ReportType", default="html")
        self.reporting_currency = self.config.get("Portfolio", "ReportingCurrency", default="AUD")
        self.reporting_currency_symbol = self.config.get("Portfolio", "ReportingCurrencySymbol", default="$")
        self.holding_display_mode = self.config.get("Portfolio", "HoldingsDisplayMode", default="both")
        self.debug = self.config.get("Files", "LogfileVerbosity") == "debug"

        # Save the path to the Portfolio Valuation file
        self.portfolio_valuation_file = None
        self.df_value_history = None  # DataFrame to hold the value history of the portfolio
        self.value_history_chart = None  # Path to the value history chart image
        csv_file_str = self.config.get("Files", "PortfolioValuationFile")
        if csv_file_str is not None:
            # Resolve the file path using the configured method
            self.portfolio_valuation_file = self.config.select_file_location(csv_file_str)

        # Initialize the portfolio
        self.holdings = []  # List of holding dict objects
        self.effective_dates = {
            "Current": DateHelper.today(),  # Current date defaults to today
            "Prior": None,
            "DaysDifference": 0,  # Number of days between prior and current valuation
        }
        self.value = {      # Total value of the portfolio
            "Current": 0.0,
            "CurrentStr": "",  # String representation of the current value
            "Prior": 0.0,
            "PriorStr": "",  # String representation of the prior value
            "ValueChange": 0.0,  # Change in value from prior to current valuation
            "ValueChangeStr": "",  # String representation of the change in value
            "ValueChangeAbsStr": "",  # String representation of the change in value without directivity
            "PcntChange": 0.0,   # Percentage change in value from prior to current valuation
            "PcntChangeStr": "",  # String representation of the percentage change
        }
        self.cost_basis = {
            "Current": 0.0,      # Total cost basis of the portfolio
            "CurrentStr": "",  # String representation of the current cost basis
            "Return": 0.0,       # Total return of the portfolio vs cost basis
            "ReturnStr": "",  # String representation of the return
        }
        self.asset_classes = []  # List of asset classes in the portfolio
        self.winners = []  # List of top winners
        self.losers = []   # List of top losers
        self.price_misses = 0  # Number of price lookup misses

        # Import portfolio data and populate the holding list
        self.portfolio_data_imports = self.config.get("Files", "PortfolioImport")
        for data_import in self.portfolio_data_imports:
            self.import_portfolio_data(data_import)

    def import_portfolio_data(self, data_import: dict):
        """
        Imports portfolio data from the configured Excel files.

        Args:
            data_import (dict): A dictionary containing the import configuration.
        """
        file_path = Path(data_import.get("DataFile"))
        data_source_name = data_import.get("NamedLocation", "Portfolio")
        data_source_type = data_import.get("LocationType", "sheet")
        min_units_held = self.config.get("Portfolio", "MinUnitsHeld", default=0.01)

        self.logger.log_message(f"Importing portfolio data from {data_source_type} {data_source_name} in {file_path}", "detailed")

        # file_path is a full path to an Excel file. Import the data from the "TablePortfolio" table in the file.
        try:
            # Create an instance of the ExcelReader class to read the Excel file
            excel_reader = ExcelReader(file_path)
            portfolio_data = excel_reader.extract_data(source_name=data_source_name, source_type=data_source_type)
        except ImportError as e:
            msg = f"Error importing portfolio data from {file_path}: {e}"
            self.logger.log_fatal_error(msg)
            return
        else:
            if portfolio_data is None:
                self.logger.log_fatal_error(f"Failed to extract portfolio data from {file_path}.")
                return

            # Inspect the first record and make sure it has the expected structure
            expected_columns = ["Symbol", "Name", "Currency", "Units Held"]
            first_entry = portfolio_data[0]
            if not all(key in first_entry for key in expected_columns):
                self.logger.log_fatal_error(f"Portfolio data from {file_path} does not have the expected structure. Expecting columns: {expected_columns}")
                return

            # Create a PortfolioValuation object and load the data
            for entry in portfolio_data:
                if entry.get("Units Held", 0.0) >= min_units_held:
                    holding = self.new_holding()
                    holding["Symbol"] = entry.get("Symbol", entry.get("Code"))
                    holding["Name"] = entry.get("Name", self.price_data.get_symbol_name(holding["Symbol"]))
                    holding["ShortDisplayName"] = self.abbreviate_holding_name(holding["Name"], holding["Symbol"])
                    holding["Class"] = entry.get("Class", "Unknown")
                    holding["Currency"] = entry.get("Currency", "AUD")
                    holding["Units Held"] = entry.get("Units Held", 0.0)
                    holding["Cost Basis"] = entry.get("Cost Basis", 0.0)
                    self.add_holding(holding)

            self.logger.log_message(f"Imported portfolio data from {file_path}", "summary")

    def new_holding(self) -> dict:  # noqa: PLR6301
        """
        Creates a new holding object with default values.

        Returns:
            new_holding (dict): A dictionary representing a new holding with default values.
        """
        new_holding = {
            "Symbol": None,           # Stock code or symbol
            "Name": None,           # Name of the stock
            "ShortDisplayName": None,  # Short display name for the stock
            "Class": None,          # Asset class of the holding
            "Currency": None,       # Currency of the holding
            "Units Held": 0.0,      # Number of units held
            "Cost Basis": 0.0,      # Cost basis for the holding
            "Current": {
                "Price": None,      # Current price of the holding
                "FX Rate": None,    # Foreign exchange rate if applicable as at the effective date
                "Value": 0.0,       # Calculated value of the holding on the valuation date
                "ValueStr": "",     # String representation of the value
            },
            "Prior": {
                "Price": None,      # Prior price of the holding
                "FX Rate": None,    # Foreign exchange rate if applicable as at the effective date
                "Value": 0.0,       # Calculated value of the holding on the valuation date
                "ValueStr": "",     # String representation of the value
            },
            "PcntChange": 0.0,  # Percentage change in value from prior to current valuation,
            "PcntChangeStr": "",  # String representation of the percentage change
        }
        return new_holding

    def add_holding(self, holding: dict):
        """
        Adds a holding to the portfolio valuation.

        Args:
            holding (dict): A dictionary representing the holding to be added.
        """
        self.holdings.append(holding)
        self.logger.log_message(f"Added holding: {holding['Symbol']} with {holding['Units Held']} units", "debug")

    def abbreviate_holding_name(self, name: str, code: str) -> str:
        """
        Abbreviates the holding name to a shorter version if it exceeds the maximum length.

        Args:
            name (str): The full name of the holding.
            code (str): The stock code or symbol of the holding.

        Returns:
            name (str): The abbreviated name if necessary, otherwise the original name.
        """
        if self.holding_display_mode == "symbol":
            return code

        max_length_px = 200
        max_length = int(round(max_length_px / 7, 0))    # Assume about 7px per char
        return_str = f"{code}: {name}" if self.holding_display_mode == "both" else name
        if len(return_str) > max_length:
            return_str = return_str[:max_length] + "..."
        return return_str

    def value_portfolio(self, mode: str) -> bool:
        """
        Calculates the total value of the portfolio as at a given date.

        Args:
            mode(str): The mode of the valuation, either "Current" or "Prior".

        Returns:
            result (bool): True if the valuation was successful, False otherwise. Also returns the number of price lookup misses.
        """
        max_price_misses = self.config.get("Portfolio", "MaxPriceMisses", default=2)
        self.price_misses = 0
        if mode == "Current":
            self.effective_dates["Current"] = DateHelper.today()
        elif mode == "Prior":
            offset_days = self.config.get("Portfolio", "PriorValuationDays", default=7)
            self.effective_dates["Prior"] = DateHelper.today_add_days(-offset_days)
        else:
            self.logger.log_fatal_error(f"Invalid mode '{mode}' specified for portfolio valuation.")
            return False

        self.value[mode] = 0.0      # Reset the total value for the mode

        # Itterate through each holding and calculate its value
        for entry in self.holdings:
            symbol = entry.get("Symbol")
            units_held = entry.get("Units Held", 0)
            currency = entry.get("Currency", "AUD")
            cost_basis = entry.get("Cost Basis", 0.0)

            # Holding is in a different currency than the reporting currency, look up the FX rate as at # the specified date
            if currency != self.reporting_currency:
                if currency == "USD":
                    yahoo_symbol = f"{self.reporting_currency}=X"
                else:
                    yahoo_symbol = f"{currency}{self.reporting_currency}=X"

                fx_rate, _ = self.price_data.get_price_on_date(yahoo_symbol, self.effective_dates[mode])
                if fx_rate is None:
                    self.logger.log_fatal_error(f"Failed to get {yahoo_symbol} FX rate on {self.effective_dates[mode]}.")

            else:
                # If the currency is in our native currency, we don't need to convert
                fx_rate = 1.0

            # Get the price for the symbol on the specified date
            price, price_currency = self.price_data.get_price_on_date(symbol, self.effective_dates[mode])
            if price is None:
                self.price_misses += 1
                symbol_value = 0
            elif price_currency is not None and price_currency != currency:
                self.logger.log_message(f"Price currency mismatch for {symbol} on {self.effective_dates[mode]}: expected {currency}, got {price_currency}. Using price as is.", "warning")
                self.price_misses += 1
                symbol_value = 0
            else:
                entry[mode]["Price"] = price
                symbol_value = units_held * price * fx_rate
                entry[mode]["FX Rate"] = fx_rate
                entry[mode]["Value"] = symbol_value
                self.value[mode] += symbol_value
                if mode == "Current":
                    self.cost_basis["Current"] += cost_basis
                self.logger.log_message(f"{symbol}: {units_held}units * {price:2f} * FX{fx_rate:6f} = {symbol_value}", "debug")

            # Now increment the asset class list if it doesn't already exist
            self.add_asset_class_value(
                asset_class=entry.get("Class", "Unknown"),
                mode=mode,
                value=symbol_value
            )

        if self.price_misses > max_price_misses:
            self.logger.log_fatal_error(f"Exceeded maximum price misses ({max_price_misses}) for {mode} valuation. Only {len(self.holdings) - self.price_misses} holdings were successfully valued.")
            return False

        self.logger.log_message(f"Valuing portfolio as at {self.effective_dates[mode]} at {self.reporting_currency_symbol}{self.value[mode]:,.0f}", "detailed")

        self.save_portfolio_valuation(mode)
        return True

    def add_asset_class_value(self, asset_class: str, mode: str, value: float) -> bool:
        """
        Adds a value to the specified asset class in the portfolio.

        Args:
            asset_class (str): The asset class to add the value to.
            mode (str): The mode of the valuation, either "Current" or "Prior".
            value(float): The value to add to the asset class.

        Returns:
            result (bool): True if the asset class was added or updated successfully, False otherwise.
        """
        # Check if the asset class already exists
        for entry in self.asset_classes:
            if entry["Class"] == asset_class:
                entry[mode] += value
                return True

        # If it doesn't exist, create a new entry
        self.asset_classes.append({
            "Class": asset_class,
            "Current": 0.0,
            "Prior": 0.0,
            "ValueChange": 0.0,
            "ValueChangeStr": "",
            "PcntChange": 0.0,
            "PcntChangeStr": "",
        })

        # Add the value to the new entry
        for entry in self.asset_classes:  # Find the newly created entry
            if entry["Class"] == asset_class:
                entry[mode] += value

        return True

    def save_portfolio_valuation(self, mode: str) -> bool:
        """
        Saves the current and prior portfolio valuations to a CSV file if configured to do so.

        Args:
            mode (str): The mode of the valuation, either "Current" or "Prior".

        Returns:
            result (bool): True if the valuation was saved successfully, False otherwise.
        """
        if self.portfolio_valuation_file is None:
            self.logger.log_message("Portfolio valuation file is not configured. Skipping save.", "detailed")
            return False

        # Make sure the date and value are set for the mode
        if self.effective_dates[mode] is None or self.value[mode] is None:
            self.logger.log_message(f"Effective date or value for mode '{mode}' is not set. Cannot save valuation.", "error")
            return False

        # Read existing CSV and remove today's rows
        existing_rows = []
        header = ["Date", "Valuation"]
        if self.portfolio_valuation_file.exists():
            with self.portfolio_valuation_file.open(newline="", encoding="utf-8") as csvfile:
                reader = csv.reader(csvfile)
                header = next(reader, None)  # Read the header
                for row in reader:
                    if row:
                        row_date = DateHelper.parse_date(row[0])
                        if row_date is None:
                            # If the date is invalid, skip this row
                            continue

                        # Convert as_at_date to date if it's a datetime
                        if row_date != self.effective_dates[mode]:
                            existing_rows.append(row)

        # Add record for the specified valuation
        new_record = [
            DateHelper.format_date(self.effective_dates[mode], "%Y-%m-%d"),
            f"{round(self.value[mode], 0)}",
        ]
        existing_rows.append(new_record)

        # Sort the rows by date in ascending order
        existing_rows.sort(key=lambda x: DateHelper.parse_date(x[0]))

        # Write updated CSV
        with self.portfolio_valuation_file.open("w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)

            # Write header
            writer.writerow(header)

            # Write previous rows (without today's duplicates)
            for row in existing_rows:
                # Ensure the first column is a date string
                row[0] = DateHelper.parse_date(row[0])
                writer.writerow(row)

        self.logger.log_message(f"Wrote valuation at {DateHelper.format_date(self.effective_dates[mode])} to {self.portfolio_valuation_file}", "detailed")
        return True

    def calculate_valuation_change(self) -> bool:
        """
        Calculates the change in portfolio valuation from prior to current.

        Returns:
            result (bool): True if the valuation change was calculated successfully, False otherwise.
        """
        self.effective_dates["DaysDifference"] = DateHelper.days_between(
            self.effective_dates["Prior"],
            self.effective_dates["Current"]
        )

        if self.value["Prior"] <= 0:
            self.logger.log_message("No prior valuation available. Cannot calculate valuation change.", "error")
            return False

        # String values for the current and prior valuations
        self.value["CurrentStr"] = self.display_cash(self.value["Current"], "abs")
        self.value["PriorStr"] = self.display_cash(self.value["Prior"], "abs")

        # Calculate the change in value and percentage change
        self.value["ValueChange"] = self.value["Current"] - self.value["Prior"]
        self.value["ValueChangeStr"] = self.display_cash(self.value["ValueChange"], "delta")
        self.value["PcntChange"] = ((self.value["Current"] - self.value["Prior"]) / self.value["Prior"]) * 100
        self.value["PcntChangeStr"] = self.display_percentage(self.value["PcntChange"], "delta")
        self.value["PcntChangeAbsStr"] = self.display_percentage(self.value["PcntChange"], "abs")

        # Calculate the cost basis return
        if self.cost_basis["Current"] > 0:
            self.cost_basis["CurrentStr"] = self.display_cash(self.cost_basis["Current"], "abs")
            self.cost_basis["Return"] = ((self.value["Current"] - self.cost_basis["Current"]) / self.cost_basis["Current"]) * 100
            self.cost_basis["ReturnStr"] = self.display_percentage(self.cost_basis["Return"], "delta")

        self.logger.log_message(f"Valuation change: {self.reporting_currency_symbol}{self.value['ValueChange']:,.0f} ({self.value['PcntChange']:.1f}%)", "detailed")
        return True

    def calculate_winners_and_losers(self) -> bool:
        """
        Calculates the top # winners and losers in the portfolio based on current valuation.

        Returns:
            result (bool): True if winners and losers were calculated successfully, False otherwise.
        """
        self.winners = []
        if not self.holdings:
            self.logger.log_message("No holdings to evaluate for winners and losers.", "warning")
            return False

        # Calculate how many winners and losers to find
        rank_size = self.config.get("Portfolio", "WinnersAndLosers", default=5)
        if rank_size > len(self.holdings) / 2:
            rank_size = round(len(self.holdings) / 2, 0)

        # Iterate through holdings to calculate percentage change
        for entry in self.holdings:
            current_value = entry["Current"]["Value"]
            prior_value = entry["Prior"]["Value"]

            if prior_value > 0:
                percent_change = ((current_value - prior_value) / prior_value) * 100
            else:
                percent_change = 0.0
            entry["PcntChange"] = percent_change

            # Labels
            entry["Current"]["ValueStr"] = self.display_cash(entry["Current"]["Value"], "abs")
            entry["Prior"]["ValueStr"] = self.display_cash(entry["Prior"]["Value"], "abs")
            entry["PcntChangeStr"] = self.display_percentage(percent_change, "delta")

        # Sort holdings by percentage change
        self.holdings.sort(key=operator.itemgetter("PcntChange"), reverse=True)
        # Flag the top winners
        for i, entry in enumerate(self.holdings):
            self.winners.append(entry)
            if i == rank_size - 1:
                break

        # Flag the top losers
        for i, entry in enumerate(reversed(self.holdings)):
            self.losers.append(entry)
            if i == rank_size - 1:
                break

        # Sort holdings by symbol change
        self.holdings.sort(key=operator.itemgetter("Symbol"))

        return True

    def calculate_asset_class_changes(self):
        """Calculates the percentage change in value for each asset class."""
        for entry in self.asset_classes:
            current_value = entry["Current"]
            prior_value = entry["Prior"]

            if prior_value > 0:
                value_change = current_value - prior_value
                percent_change = (value_change / prior_value) * 100
            else:
                value_change = 0.0
                percent_change = 0.0

            entry["ValueChange"] = value_change
            entry["ValueChangeStr"] = self.display_cash(value_change, "delta")
            entry["PcntChange"] = percent_change
            entry["PcntChangeStr"] = self.display_percentage(percent_change, "delta")

        # Sort asset classes by name
        # self.asset_classes.sort(key=lambda x: x["PcntChange"], reverse=True)
        self.asset_classes.sort(key=operator.itemgetter("Class"))

    def display_cash(self, value: float, mode: str = "normal") -> str:
        """
        Formats the cash value for display.

        Args:
            value (float): The cash value to format.
            mode (str): The display mode, one of abs, delta, normal.

        Returns:
            value (str): The formatted cash value as a string.
        """
        currency_symbol = self.reporting_currency_symbol
        if value is None:
            return "N/A"

        # If it's a delta, format it with a sign
        if mode == "delta":
            if value > 0:
                return f"+{currency_symbol}{value:,.0f}"
            if value < 0:
                return f"-{currency_symbol}{abs(value):,.0f}"
            return "No change"

        # Display the value as absolute
        if mode == "abs":
            return f"{currency_symbol}{abs(value):,.0f}"

        # Default to normal display with sign
        if value < 0:
            return f"-{currency_symbol}{abs(value):,.0f}"
        return f"{currency_symbol}{value:,.0f}"

    def display_percentage(self, value: float, mode: str = "normal") -> str:  # noqa: PLR6301
        """
        Formats the percentage value for display.

        Args:
            value (float): The cash value to format.
            mode (str): The display mode, one of abs, delta, normal.

        Returns:
            value (str): The formatted percentage value as a string.
        """
        if value is None:
            return "N/A"

        # If it's a delta, format it with a sign
        if mode == "delta":
            if value > 0:
                return f"+{value:,.1f}%"
            if value < 0:
                return f"-{abs(value):,.1f}%"
            return "No change"

        # Display the value as absolute
        if mode == "abs":
            return f"{abs(value):,.1f}%"

        # Default to normal display with sign
        if value > 0:
            return f"+{value:.1f}%"
        return f"{value:.1f}%"

    def send_text_report(self):
        """Issues a report summarizing the portfolio valuation changes."""
        report_path = self.config.select_file_location("reports/PortfolioValuationReport.txt")

        summary_message = f"Portfolio {self.effective_dates["DaysDifference"]} day move: {self.display_cash(self.value['ValueChange'], "delta")} ({self.display_percentage(self.value['PcntChange'], "delta")}). "
        summary_message += f"Current valuation: {self.display_cash(self.value['Current'])}."

        # If cost basis isn't zero, calculate the percentage change from cost basis
        if self.cost_basis["Current"] > 0:
            summary_message += f" Cost basis: {self.display_cash(self.cost_basis["Current"])} ({self.display_percentage(self.cost_basis["Return"], "delta")})."

        self.logger.log_message(summary_message, "summary")

        # Add price misses to the summary
        if self.price_misses > 0:
            summary_message += f"\n\nWARNING: {self.price_misses} price lookup misses occurred during valuation."

        # List the asset classes and their changes
        summary_message += "\n\nAsset Classes:\n"
        for entry in self.asset_classes:
            summary_message += f"{entry["Class"]}: {self.display_cash(entry["ValueChange"], "delta")} ({self.display_percentage(entry["PcntChange"], "abs")}) Value: {self.display_cash(entry["Current"])}\n"

        # List top winners and losers
        summary_message += f"\n\nTop {len(self.winners)} winners:\n"
        for entry in self.winners:
            summary_message += f"{entry['Name']} ({entry['Symbol']}): Value: {self.display_cash(entry['Current']['Value'])} ({self.display_percentage(entry['PcntChange'], "delta")})\n"

        summary_message += f"\nTop {len(self.winners)} losers:\n"
        for entry in self.losers:
            summary_message += f"{entry['Name']} ({entry['Symbol']}): Value: {self.display_cash(entry['Current']['Value'])} ({self.display_percentage(entry['PcntChange'], "delta")})\n"

        # Save the report text to a text file
        try:
            with report_path.open("w", encoding="utf-8") as file:
                file.write(summary_message)
            self.logger.log_message(f"Portfolio text report saved to {report_path}", "detailed")
        except OSError as e:
            self.logger.log_fatal_error(f"Failed to save portfolio report: {e}")

        # Finally send the report via email if configured
        self.logger.send_email(
            self.report_name,
            report_path,
        )

        # And delete the report file if configured to do so
        if not self.config.get("Files", "SaveReportOutputFiles", default=False):
            self.logger.log_message(f"Deleting the intermediary report file {report_path}", "debug")
            report_path.unlink()

    def get_value_history(self) -> bool:
        """
        Retrieves the historical values of the portfolio from the configured valuation file.

        Returns:
            result (bool): True if the historical values were retrieved successfully, False otherwise.
        """
        if self.portfolio_valuation_file is None:
            self.logger.log_message("Portfolio valuation file is not configured. Skipping value history retrieval.", "debug")
            return False

        if not self.portfolio_valuation_file.exists():
            self.logger.log_message("Portfolio valuation file not yet available. Skipping value history retrieval.", "debug")
            return False

        # Load and parse the valuation history CSV
        try:
            df_values = pd.read_csv(self.portfolio_valuation_file, dayfirst=True)

        except pd.errors.EmptyDataError:
            self.logger.log_fatal_error(f"Portfolio valuation file {self.portfolio_valuation_file} is empty.")
            return False

        df_values["Date"] = pd.to_datetime(df_values["Date"], format="%Y-%m-%d")
        df_values = df_values.sort_values("Date")

        # Filter to last 365 days
        cutoff_days = self.config.get("HistoryChart", "ChartNumberOfDays", default=365)
        # cutoff_date = DateHelper.today_add_days(-cutoff_days)
        # cutoff_date = datetime.combine(cutoff_date, datetime.min.time())
        cutoff_date = datetime.now() - timedelta(days=cutoff_days)  # noqa: DTZ005
        self.df_value_history = df_values[df_values["Date"] >= cutoff_date]

        return True

    def generate_value_chart(self) -> bool:  # noqa: PLR0915
        """
        Generates a value chart of the portfolio valuation.

        Returns:
            result (bool): True if the chart was generated successfully, False otherwise.
        """
        if not self.config.get("HistoryChart", "EnableCloudinary", default=False):
            self.logger.log_message("Cloudinary is not enabled for history chart generation. Skipping chart generation.", "debug")
            return False

        if not self.get_value_history():
            # No portfolio value history available, already logged
            return False

        if self.portfolio_valuation_file is None:
            self.logger.log_message("Portfolio valuation file is not configured. Skipping value history retrieval.", "debug")
            return False

        # Load Cloudinary credentials
        try:
            load_dotenv()

            cloudinary.config(
                cloud_name=self.config.get("HistoryChart", "CloudName"),
                api_key=self.config.get("HistoryChart", "APIKey"),
                api_secret=self.config.get("HistoryChart", "APISecret"),
            )
        except cloudinary.exceptions.Error as e:
            self.logger.log_fatal_error(f"Failed to configure Cloudinary: {e}")
            return False

        # Plotting
        plt.figure(figsize=(12, 6))
        ax = plt.gca()

        # Line plot with branding color
        ax.plot(
            self.df_value_history["Date"],
            self.df_value_history["Valuation"],
            color="#1f77b4", linewidth=2.5, marker="o", markersize=5, label="Value"
        )

        # Styling
        title = self.config.get("HistoryChart", "ChartTitle", default="Portfolio Valuation (last 12 months)")
        ax.set_title(title, fontsize=14, fontweight="bold", color="darkgray")
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)

        # Format x-axis dates
        # ax.set_xlabel("Date", fontsize=12)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        plt.xticks(rotation=45, ha="right")

        # Format y-axis as currency
        ax.set_ylabel("Net Value", fontsize=12)
        ax.yaxis.set_major_formatter(mtick.FuncFormatter(currency_thousands))

        # Borders
        # plt.tight_layout(pad=1.0)  # Automatically adjusts spacing, 'pad' controls padding
        plt.subplots_adjust(left=0.08, right=0.98, top=0.92, bottom=0.12)

        # Remove chart frame spines
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)

        # Add Spello Consulting branding text or logo
        brand_text = self.config.get("HistoryChart", "BrandText", default="©Spello Consulting")
        if brand_text:
            plt.text(
                0.99, 0.02,
                "©Spello Consulting",
                fontsize=10,
                color="gray",
                ha="right",
                va="bottom",
                transform=ax.transAxes
            )

        # Save image with unique filename
        image_filename = f"reports/valuation_{uuid.uuid4().hex}.png"
        plt.savefig(image_filename)
        plt.close()

        # Upload to Cloudinary
        try:
            upload_result = cloudinary.uploader.upload(image_filename, folder="portfolio_charts/")
            image_url = upload_result["secure_url"]
        except cloudinary.exceptions.AuthorizationRequired as e:
            self.logger.log_fatal_error(f"Cloudinary authorization error when uploading chart image: {e}")
        except cloudinary.exceptions.NotFound as e:
            self.logger.log_fatal_error(f"Cloudinary resource not found error when uploading chart image: {e}")
        except cloudinary.exceptions.BadRequest as e:
            self.logger.log_fatal_error(f"Cloudinary bad request error when uploading chart image: {e}")
        except cloudinary.exceptions.Error as e:
            error_text = str(e)
            # Find the start of the HTML and truncate before it
            html_start = error_text.find("b'<!DOCTYPE html>")
            if html_start != -1:
                error_text = error_text[:html_start].strip()
            self.logger.log_fatal_error(f"Cloudinary error when uploading chart image: {e}")
        else:
            self.logger.log_message(f"Chart image uploaded to Cloudinary: {image_url}", "debug")
            self.value_history_chart = image_url

            # If saving reports locally is enabled, rename the image file
            if self.config.get("Files", "SaveReportOutputFiles", default=True):
                Path("reports/valuation.png").unlink(missing_ok=True)  # Remove any existing file
                Path(image_filename).rename("reports/valuation.png")
            else:
                self.logger.log_message(f"Deleting the intermediary chart file {image_filename}", "debug")
                Path(image_filename).unlink(missing_ok=True)

        return True

    def send_html_report(self) -> bool:
        """
        Generates an HTML report of the portfolio valuation.

        Returns:
            result (bool): True if the HTML report was generated and sent successfully, False otherwise.
        """
        # Generate the value chart if not already done
        if self.generate_value_chart():
            self.logger.log_message("Value chart generated successfully.", "debug")

        # Get the path to the HTML report file
        report_template_path = self.config.select_file_location(self.config.get("Files", "ReportHTMLTemplate", default=None))
        report_path = self.config.select_file_location("reports/PortfolioValuationReport.html")
        if report_template_path is None:
            self.logger.log_message("No report template configured. Skipping HTML report generation.", "detailed")
            return False

        # data = {
        #     "page_title": "Portfolio Valuation Report",
        # }

        # Create a dictionary with the data to be rendered in the template
        data = self.__dict__.copy()

        # Get the folder and filename of the report template
        report_template_folder = Path(report_template_path).parent
        report_template_filename = Path(report_template_path).name

        # Create a Jinja2 environment and load the template
        env = Environment(
            loader=FileSystemLoader(report_template_folder),
            autoescape=True
        )

        # Render the output HTML with the data and template
        try:
            template = env.get_template(report_template_filename)
            rendered_html = template.render(data)
        except TemplateError as e:
            self.logger.log_fatal_error(f"Failed to render HTML report template: {e}")
            return False

        # Save the report text to a text file
        try:
            with report_path.open("w", encoding="utf-8") as file:
                file.write(rendered_html)
            self.logger.log_message(f"Portfolio HTML report saved to {report_path}", "detailed")
        except OSError as e:
            self.logger.log_fatal_error(f"Failed to save portfolio report: {e}")

        # Finally send the report via email if configured
        self.logger.send_email(
            self.report_name,
            report_path,
        )

        # And delete the report file if configured to do so
        if not self.config.get("Files", "SaveReportOutputFiles", default=False):
            self.logger.log_message(f"Deleting the intermediary report file {report_path}", "debug")
            report_path.unlink()

        return True
