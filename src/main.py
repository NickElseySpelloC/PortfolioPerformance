"""Send out scheduled email reporting on the change in portfolio value."""
import argparse
import os
import sys
from pathlib import Path

from sc_utility import SCCommon, SCConfigManager, SCLogger

from config_schemas import ConfigSchema
from portfolio import PortfolioManager
from price_data import PriceDataManager

CONFIG_FILE = "config.yaml"


def parse_command_line_args() -> dict[str, str | None]:
    """Parse and validate command line arguments.

    Returns:
        dict: Dictionary containing parsed arguments with keys:
            - 'config_file': Path to configuration file (always present)
            - 'homedir': Project home directory (for logging purposes, may be None)

    Exits:
        Exits with code 1 if arguments are invalid.
    """
    parser = argparse.ArgumentParser(
        description="Portfolio Performance - Portfolio valuation and reporting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 src/main.py
  python3 src/main.py --units weeks --quantity 2
  python3 src/main.py --units months --quantity 3 --use-current-date
  python3 src/main.py --config /path/to/config.yaml --units quarters --quantity 1
  python3 src/main.py --homedir /opt/portfolio --config config.yaml --units years --quantity 1
        """
    )

    parser.add_argument(
        "--homedir",
        type=str,
        metavar="PATH",
        help="Specify the project home directory",
    )

    parser.add_argument(
        "--config",
        type=str,
        metavar="FILE",
        help=f"Path to configuration file (default: {CONFIG_FILE})",
    )

    parser.add_argument(
        "--units",
        type=str,
        metavar="UNITS",
        default="days",
        choices=["days", "weeks", "months", "quarters", "years"],
        help="Reporting period units (default: days). Choices: days, weeks, months, quarters, years",
    )

    parser.add_argument(
        "--quantity",
        type=int,
        metavar="N",
        default=7,
        help="Quantity of reporting period units (default: 7)",
    )
    args = parser.parse_args()

    # Determine the base directory for resolving relative paths
    if args.homedir:
        homedir = Path(args.homedir)
        if not homedir.exists():
            print(f"ERROR: Specified homedir does not exist: {args.homedir}", file=sys.stderr)
            sys.exit(1)
        if not homedir.is_dir():
            print(f"ERROR: Specified homedir is not a directory: {args.homedir}", file=sys.stderr)
            sys.exit(1)
        base_dir = homedir.resolve()

        # Set the project root environment variable for use by SC_Utility and other components
        os.environ["SC_UTILITY_PROJECT_ROOT"] = str(base_dir)
    else:
        base_dir = Path(SCCommon.get_project_root())

    # Determine the config file path
    if args.config:
        config_path = Path(args.config)
        # If relative path, resolve it relative to base_dir
        if not config_path.is_absolute():
            config_path = base_dir / config_path
        config_file = str(config_path.resolve())

        # Validate that the config file exists
        if not Path(config_file).exists():
            print(f"ERROR: Configuration file does not exist: {config_file}", file=sys.stderr)
            sys.exit(1)
        if not Path(config_file).is_file():
            print(f"ERROR: Configuration path is not a file: {config_file}", file=sys.stderr)
            sys.exit(1)
    else:
        config_file = CONFIG_FILE

    return {
        "config_file": config_file,
        "homedir": str(base_dir) if args.homedir else None,
        "units": args.units,
        "quantity": args.quantity,
    }


def main():
    """Main function to run the Portfolio Performance app."""
    # Parse command line arguments
    cmd_args = parse_command_line_args()

    # Get our default schema, validation schema, and placeholders
    schemas = ConfigSchema()

    # Initialize the SCConfigManager class
    try:
        config_file = cmd_args["config_file"]
        assert isinstance(config_file, str), "config_file must be a string"

        # make sure the config file exists before trying to initialize SCConfigManager, so that we can provide a clear error message if it doesn't
        if not Path(config_file).exists():
            print(f"ERROR: Configuration file does not exist: {config_file}", file=sys.stderr)
            sys.exit(1)

        config = SCConfigManager(
            config_file=config_file,
            default_config=schemas.default,
            validation_schema=schemas.validation,
            placeholders=schemas.placeholders
        )
    except RuntimeError as e:
        print(f"Configuration file error: {e}", file=sys.stderr)
        sys.exit(1)     # Exit with errorcode 1 so that launch.sh can detect it

    # Initialize the SCLogger class
    try:
        logger = SCLogger(config.get_logger_settings())
    except RuntimeError as e:
        print(f"Logger initialisation error: {e}", file=sys.stderr)
        sys.exit(1)     # Exit with errorcode 1 so that launch.sh can detect it

    logger.log_message("Starting Portfolio Performance app", "summary")

    # Setup email
    logger.register_email_settings(config.get_email_settings())

    # Create the PriceDataManager instance and read the price data files
    price_data = PriceDataManager(config, logger, schemas.price_csv_header_config)

    # Create the PortfolioManager instance and read the portfolio data file
    portfolio = PortfolioManager(config, logger, price_data)

    # Set the reporting period for the portfolio manager based on command line args
    units = cmd_args["units"]
    quantity = cmd_args["quantity"]
    assert isinstance(units, str), "units must be a string"
    assert isinstance(quantity, int), "quantity must be an integer"

    # interval_end=True means use natural period end, False means use current date
    period_dates = portfolio.set_reporting_period(units=units, quantity=quantity)
    logger.log_message(f"Reporting period: {quantity} {units}, dates: {period_dates['StartDate']} to {period_dates['EndDate']}", "summary")

    # Get the prior and current portfolio valuations
    if not portfolio.value_portfolio("Prior"):
        logger.log_fatal_error("No prior valuation available. Cannot proceed with valuation change report.")

    if not portfolio.value_portfolio("Current"):
        logger.log_fatal_error("No current valuation available. Cannot proceed with valuation change report.")

    portfolio.calculate_valuation_change()
    portfolio.calculate_winners_and_losers()
    portfolio.calculate_asset_class_changes()

    # And send out the valuation change report
    if portfolio.report_type in {"text", "both"}:
        portfolio.send_text_report()
    if portfolio.report_type in {"html", "both"}:
        portfolio.send_html_report()

    # If the prior run fails, send email that this run worked OK
    if logger.get_fatal_error():
        logger.log_message(
            "Run was successful after a prior failure.", "summary"
        )
        logger.send_email(
            "Run recovery",
            "InvestSmartExport run was successful after a prior failure.",
        )
        logger.clear_fatal_error()


if __name__ == "__main__":
    main()
