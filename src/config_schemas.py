"""Configuration schemas for use with the SCConfigManager class."""


class ConfigSchema:
    """Base class for configuration schemas."""

    def __init__(self):
        self.default = {
            "Portfolio": {
                "ReportName": "Portfolio Performance Report",
                "ReportType": "html",
                "ReportingCurrency": "AUD",
                "ReportingCurrencySymbol": "$",
                "PriorValuationDays": 7,
                "WinnersAndLosers": 5,
                "HoldingsDisplayMode": "symbol",
                "MaxPriceMisses": 2,
                "MinUnitsHeld": 0.01,
            },
            "HistoryChart": {
                "EnableCloudinary": False,
                "CloudName": "<Your Cloud Name here>",
                "APIKey": "<Your API Key here>",
                "APISecret": "<Your API Secret here>",
                "UploadFolder": "portfolio_reports",
                "ChartTitle": "Portfolio Valuation (last 12 months)",
                "BrandText": "©Spello Consulting",
                "ChartNumberOfDays": 365,
            },
            "Files": {
                "LogfileName": "logfile.log",
                "LogfileMaxLines": 500,
                "LogfileVerbosity": "detailed",
                "ConsoleVerbosity": "summary",
                "PriceDataFiles": [
                    {
                    "DataFile": "yahoo_price_data.csv",
                    "MaxAge": 5,
                },
                    {
                    "DataFile": "investsmart_price_data.csv",
                    "MaxAge": 5,
                }
                ],
                "PortfolioValuationFile": "portfolio_valuation.csv",
                "PortfolioImport": [
                    {
                        "DataFile": "portfolio.xlsx",
                        "NamedLocation": "Portfolio",
                        "LocationType": "sheet",
                    },
                ],
                "ReportTemplate": "report_template.html",
                "SaveReportOutputAsFiles": True,
            },
            "Email": {
                "EnableEmail": False,
                "SendEmailsTo": None,
                "SMTPServer": None,
                "SMTPPort": None,
                "SMTPUsername": None,
                "SMTPPassword": None,
                "SubjectPrefix": None,
            },
        }

        self.placeholders = {
            "HistoryChart": {
                "CloudName": "<Your Cloud Name here>",
                "APIKey": "<Your API Key here>",
                "APISecret": "<Your API Secret here>",
            },
            "Email": {
                "SendEmailsTo": "<Your email address here>",
                "SMTPUsername": "<Your SMTP username here>",
                "SMTPPassword": "<Your SMTP password here>",
            }
        }

        self.validation = {
            "Portfolio": {
                "type": "dict",
                "schema": {
                    "ReportName": {"type": "string", "required": False, "nullable": True},
                    "ReportType": {"type": "string", "required": False, "nullable": True},
                    "ReportingCurrency": {"type": "string", "required": False, "nullable": True},
                    "ReportingCurrencySymbol": {"type": "string", "required": False, "nullable": True},
                    "PriorValuationDays": {"type": "number", "required": False, "nullable": True},
                    "WinnersAndLosers": {"type": "number", "required": False, "nullable": True},
                    "HoldingsDisplayMode": {"type": "string", "required": False, "nullable": True},
                    "MaxPriceMisses": {"type": "number", "required": False, "nullable": True},
                    "MinUnitsHeld": {"type": "number", "required": False, "nullable": True},
                }
            },
            "HistoryChart": {
                "type": "dict",
                "schema": {
                    "EnableCloudinary": {"type": "boolean", "required": True},
                    "CloudName": {"type": "string", "required": False, "nullable": True},
                    "APIKey": {"type": "string", "required": False, "nullable": True},
                    "APISecret": {"type": "string", "required": False, "nullable": True},
                    "UploadFolder": {"type": "string", "required": False, "nullable": True},
                    "ChartTitle": {"type": "string", "required": False, "nullable": True},
                    "BrandText": {"type": "string", "required": False, "nullable": True},
                    "ChartNumberOfDays": {"type": "number", "required": False, "nullable": True, "min": 1, "max": 365},
                }
            },
            "Files": {
                "type": "dict",
                "schema": {
                    "LogfileName": {"type": "string", "required": False, "nullable": True},
                    "LogfileMaxLines": {"type": "number", "min": 0, "max": 100000},
                    "LogfileVerbosity": {
                        "type": "string",
                        "required": True,
                        "allowed": ["none", "error", "warning", "summary", "detailed", "debug", "all"],
                    },
                    "ConsoleVerbosity": {
                        "type": "string",
                        "required": True,
                        "allowed": ["error", "warning", "summary", "detailed", "debug", "all"],
                    },
                    "PriceDataFiles": {
                        "type": "list",
                        "required": True,
                        "nullable": False,
                        "schema": {
                            "type": "dict",
                            "schema": {
                                "DataFile": {"type": "string", "required": True},
                                "MaxAge": {"type": "number", "required": False, "nullable": True},
                            },
                        },
                    },
                    "PortfolioValuationFile": {"type": "string", "required": False, "nullable": True},
                    "PortfolioImport": {
                        "type": "list",
                        "required": True,
                        "nullable": False,
                        "schema": {
                            "type": "dict",
                            "schema": {
                                "DataFile": {"type": "string", "required": True},
                                "NamedLocation": {"type": "string", "required": True},
                                "LocationType": {
                                    "type": "string",
                                    "required": True,
                                    "allowed": ["sheet", "table", "range"]
                                },
                            },
                        },
                    },
                    "ReportHTMLTemplate": {"type": "string", "required": False, "nullable": True},
                    "SaveReportOutputFiles": {"type": "boolean", "required": False, "nullable": True},
                 },
            },
            "Email": {
                "type": "dict",
                "schema": {
                    "EnableEmail": {"type": "boolean", "required": True},
                    "SendEmailsTo": {"type": "string", "required": False, "nullable": True},
                    "SMTPServer": {"type": "string", "required": False, "nullable": True},
                    "SMTPPort": {"type": "number", "required": False, "nullable": True, "min": 25, "max": 1000},
                    "SMTPUsername": {"type": "string", "required": False, "nullable": True},
                    "SMTPPassword": {"type": "string", "required": False, "nullable": True},
                    "SubjectPrefix": {"type": "string", "required": False, "nullable": True},
                },
            },
        }

        self.price_csv_header_config = [
            {
                "name": "Symbol",
                "type": "str",
                "sort": 2,
            },
            {
                "name": "Date",
                "type": "date",
                "format": "%Y-%m-%d",
                "sort": 1,
            },
            {
                "name": "Name",
                "type": "str",
            },
            {
                "name": "Currency",
                "type": "str",
            },
            {
                "name": "Price",
                "type": "float",
                "format": ".2f",
            },
        ]
