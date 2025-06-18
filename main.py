"""Send out scheduled email reporting on the change in portfolio value."""
import sys

from sc_utility import SCConfigManager, SCLogger

from config_schemas import ConfigSchema
from portfolio import PortfolioManager
from price_data import PriceDataManager

CONFIG_FILE = "config.yaml"

def main():
    """Main function to run the Portfolio Performance app."""
    # Get our default schema, validation schema, and placeholders
    schemas = ConfigSchema()

    # Initialize the SCConfigManager class
    try:
        config = SCConfigManager(
            config_file=CONFIG_FILE,
            default_config=schemas.default,
            validation_schema=schemas.validation,
            placeholders=schemas.placeholders
        )
    except RuntimeError as e:
        print(f"Configuration file error: {e}", file=sys.stderr)
        return

    # Initialize the SCLogger class
    try:
        logger = SCLogger(config.get_logger_settings())
    except RuntimeError as e:
        print(f"Logger initialisation error: {e}", file=sys.stderr)
        return

    logger.log_message("Starting Portfolio Performance app" , "summary")

    # Setup email
    logger.register_email_settings(config.get_email_settings())

    # Create the PriceDataManager instance and read the price data files
    price_data = PriceDataManager(config, logger)

    # Create the PortfolioManager instance and read the portfolio data file
    portfolio = PortfolioManager(config, logger, price_data)

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
    if portfolio.report_type in ("html", "both"):
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
