# Portfolio Performance Reporting
This app generates a simple performance report for your investment portfolio, including:
- Overall change in value over the past # days
- Change in value of each asset class 
- Top N winners - the individual holdings that have improved the most over the past # days
- Top N losers

## Input Files
This app needs two input data sources:
1. Portfolio Holdings: An Excel file listing the individual holdings (stocks, funds, cash) in your investment portfolio. 
2. Price Data Files: One or more CSV files providing current and historic price data for the stocks and funds in your investment portfolio. These data can be obtained from Yahoo Finance, etc. 

See below for more information.

## Portfolio Holdings File(s)
These must be Excel file(s) containing one or more data ranges that collectively defined the current holdings in your investment portfolio. You can import portfolio data from one or more Excel files and/or ranges. 

Each range in the Excel file can be one of:
- An entire worksheet, or
- An Excel table, or
- A named range

The following columns are expected in each import range:
**Symbol**: The symbol (code) for the holding, as used in the Price Data files. For example _MSFT_. If the holding is cash, use CASH as the symbol. 

**Name**: The name of this holding, for example _Microsoft, Inc._

**Class**: The asset class that this holding falls in. This can be any arbitary name that you use to categorise your portfolio holdings into, for example _Equities: International_

**Currency**: The currency that this investment is denominated in, for example _USD_

**Units Held**: The number of units / shares you currently hold, for example: _1000_

**Cost Basis**: The total cost basis for your entire holding, as stated in the base (reporting) currency, for example _352300_. 

The Cost Basis column is optional, everything else is required.

The path to your Portfolio Holdings files is specified in the _PortfolioImport_ section of the config file (see below).

## Price Data Files
These must be CSV file(s) containing a range of historic prices for stocks and funds that you hold. The files can hold any amount of history but must go back at least the number of days covering the comparision period of the report.  

The app will uses these data to lookup the current and prior price for each holding, plus FX rates to convert international holdings to your base currency. If a record isn't available for the specific date that we are pricing a portfolio for, the app will use the most recent price prior to that date.

The following columns are expected in CSV file:
**Symbol**: The symbol (code) for the holding, for example _MSFT_. For FX rates, the symbol must be in the format used by Yahoo Finance, for example _AUDUSD=X_ to convert from AUD to USD, or _GBP=X_ to convert from USD to GBP.
  
**Date**: The effective date of this price, in the format YYYY-MM-DD, for example 2025-05-07 for 7th July 2025.

**Name**: The name of this holding, for example _Microsoft, Inc._

**Currency**: The currency that this investment is denominated in, for example _USD_

**Pric**: The price of this asset as at the specified date.

Please see these apps which can be used to download historic price data:
**[YahooFinance](https://github.com/NickElseySpelloC/YahooFinance)**: Download price data from Yahoo Finance.

**[InvestSmartExport](https://github.com/NickElseySpelloC/InvestSmartExport)**: Download Australias wholesale fund prices from InvestSmart

# Installation & Setup
## Prerequisites
* Python 3.x installed:
macOS: `brew install python3`
Windows: `inget install python3 --source winget --scope machine`
* UV for Python installed:
macOS: 'brew install uvicorn'
Windows: ``pip install uv`

The shell script used to run the app (*launch.sh*) is uses the *uv sync* command to ensure that all the prerequitie Python packages are installed in the virtual environment.

## Running on Mac
If you're running the Python script on macOS, you need to allow the calling application (Terminal, Visual Studio) to access devices on the local network: *System Settings > Privacy and Security > Local Network*

# Configuration File 
The script uses the *config.yaml* YAML file for configuration. An example of included with the project (*config.yaml.example*). Copy this to *config.yaml* before running the app for the first time.  Here's an example config file:

    Portfolio:
        ReportName: "Portfolio Performance Report"
        ReportType: "html"
        ReportingCurrency: AUD
        ReportingCurrencySymbol: $
        PriorValuationDays: 14
        WinnersAndLosers: 5
        HoldingsDisplayMode: symbol
        MaxPriceMisses: 2
        MinUnitsHeld: 0.01
    
    HistoryChart:
      EnableCloudinary: True
      CloudName: "<Your Cloud Name here>"
      APIKey: "<Your API Key here>"
      APISecret: "<Your API Secret here>"
      UploadFolder: portfolio_reports
      ChartTitle: "Portfolio Valuation (last 12 months)"
      BrandText: "©Spello Consulting"
      ChartNumberOfDays: 365

    Files:
        LogfileName: logfile.log
        LogfileMaxLines: 500
        LogfileVerbosity: detailed
        ConsoleVerbosity: detailed
        PriceDataFiles:
            - DataFile: /Users/bob/YahooFinance/price_data.csv
              MaxAge: 4
            - DataFile: /Users/bob/InvestSmartExport/price_data.csv
              MaxAge: 4
            - DataFile: manual_price_data.csv
              MaxAge: 0
        PortfolioImport:
            - DataFile: /Users/bob/my_portfolio/portfolio.xlsx
              NamedLocation: TableInvestments
              LocationType: table
            - DataFile: /Users/bob/my_portfolio/portfolio.xlsx
              NamedLocation: TableCash
              LocationType: table
        PortfolioValuationFile: /Users/bob/my_portfolio/portfolio_valuation.csv
        ReportHTMLTemplate: reports/report_template.html
        SaveReportOutputFiles: True

    Email:
        EnableEmail: True
        SMTPServer: smtp.gmail.com
        SMTPPort: 587
        SMTPUsername: me@gmail.com
        SMTPPassword: <Your SMTP password>
        SubjectPrefix: "[Bob Portfolio]: "


## Configuration Parameters
### Section: Portfolio

| Parameter | Description | 
|:--|:--|
| ReportName | The name of the report. |
| ReportType | Which format to use when sending the report. Options: html, text, both. |
| ReportingCurrency | What is the base currency for the portfolio? This is used to convert all values to a common currency. |
| ReportingCurrencySymbol | What is the symbol for the base currency? This is used to display the currency in the report. |
| PriorValuationDays | Compare the current portfolio valuation to value [PriorValuationDays] days prior. Default is 7 days. |
| WinnersAndLosers | Number of individual securities to list in the winners and losers section. |
| HoldingsDisplayMode | When individual securities are listed in the report, how should they be displayed? One of: symbol; name; both (default) |
| MaxPriceMisses | Maximum number of times we can fail to get a price for a security before we report a critical error. | 
| MinUnitsHeld | If a security has less than this many units, we will not report it in the portfolio valuation. | 

### Section: HistoryChart

Optionally you can include a line chart showing the historic value of your portfolio. To use this feature you will need to setup a free Cloudinary (cloudinary.com) account that the app will use to host the chart images which will then be included in the HTML format email. Once you have your account, go to Settings > API Keys and create a new API key for this app. Note the Cloud Name (top of that page), the API Key and API Secret and configure those values in this section of the config file.

| Parameter | Description | 
|:--|:--|
| EnableCloudinary | If true a portfolio valuation chart will be uploaded to Cloudinary and included in the report. |
| CloudName | Your Cloudinary cloud name. Find this at Settings > API Keys at the top of the page. |
| APIKey | Your Cloudinary API Key for this app. |
| APISecret | Your Cloudinary API Secret for this app. |
| UploadFolder | The folder in Cloudinary to upload the report to. |
| ChartTitle | The title to use for the history chart. |
| BrandText | Branding text to use in the chart. |
| ChartNumberOfDays | Number of prior days to include in the history chart. Defaults to 365 |

### Section: Files

| Parameter | Description | 
|:--|:--|
| LogfileName | The name of the log file, can be a relative or absolute path. | 
| LogfileMaxLines | Maximum number of lines to keep in the log file. If zero, file will never be truncated. | 
| LogfileVerbosity | The level of detail captured in the log file. One of: none; error; warning; summary; detailed; debug; all | 
| ConsoleVerbosity | Controls the amount of information written to the console. One of: error; warning; summary; detailed; debug; all. Errors are written to stderr all other messages are written to stdout | 
| PriceDataFiles | A list of the Price Data CSV file(s) to import. Each entry has the following parameters:<br>**DataFile**: Absolute or relative path to the CSV file.<br>**MaxAge**: How many days since this file was last updated before we issue a warning that the file is out of date. | 
| PortfolioImport | A list of the Excel file(s) to import the invest portfolio from. Each entry has the following paramters: <br>**DataFile**: Absolute or relative path to the Excel file.<br>**NamedLocation**: The name of the data range in the file. <br>**LocationType**: The type of location reference for the PortfolioData parameter. Must be one of: sheet, table or range. | 
| PortfolioValuationFile | Optionally, an absolute or relative path to a output CSV file. If set, each portfolio valuation will be appended to this file. | 
| ReportHTMLTemplate | The location of the html template used to generate the HTML format portfolio report. By default this lives in the reports/ sub-directory. |
| SaveReportOutputFiles | If true, a copy of the last html and/or text portfolio reports generated will be written to the reports/ sub-directory. | 

### Section: Email

| Parameter | Description | 
|:--|:--|
| EnableEmail | Set to *True* if you want to allow the app to send emails. If True, the remaining settings in this section must be configured correctly. | 
| SMTPServer | The SMTP host name that supports TLS encryption. If using a Google account, set to smtp.gmail.com |
| SMTPPort | The port number to use to connect to the SMTP server. If using a Google account, set to 587 |
| SMTPUsername | Your username used to login to the SMTP server. If using a Google account, set to your Google email address. |
| SMTPPassword | The password used to login to the SMTP server. If using a Google account, create an app password for the app at https://myaccount.google.com/apppasswords  |
| SubjectPrefix | Optional. If set, the app will add this text to the start of any email subject line for emails it sends. |

