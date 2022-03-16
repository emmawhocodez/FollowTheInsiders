import smtplib, ssl
import config
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager

#returns a list of URLS to webscrape for individual stocks transactions.
#Only traders with a 25%+ return rate are considered here
def get_trader_urls(driver):
    driver.get("https://www.tipranks.com/analysts/top")

    traders_info = driver.find_elements_by_class_name('client-components-experts-list-persons-list__li')
    trader_urls = []
    for i in traders_info:
        trader_info = i.text.split('\n')
        href = i.find_element_by_tag_name('a').get_attribute('href')
        return_rate = trader_info[12][1:-1]
        if float(return_rate) > 25.0:
            trader_urls.append(href)
    return trader_urls

#looks at recent transactions (no more than 15 days old)
#if the transaction is a buy or sell, returns the date and the ticket
def get_trader_transactions(driver, url):
    driver.get(url)
    stocks = driver.find_elements_by_class_name('client-components-experts-infoTable-expertTable__dataRow')
    transactions = ''
    for i in stocks:

        trade_info = i.text.split('\n')
        ticket, option, date = trade_info[0], trade_info[2], trade_info[5]

        if option == 'Buy' or option == 'Sell':
            if 'days' in date and 10 > int(date[0:2]):
                transactions = transactions + f'{date}    {ticket}    {option}\n'
    return transactions

#sends email with information
def send_email(email_contents):
    smtp_server = "smtp.gmail.com"
    content =  f'SUBJECT: {config.message}\n\n{email_contents}'
    server = smtplib.SMTP(smtp_server, 587)
    try:
        server.ehlo()
        server.starttls()

        server.login(config.username, config.password)
        server.sendmail(config.sender, config.recipients, content)
        server.close()

    except Exception as e:
        print(e)
        server.close()


def get_insider_transactions(driver):
    driver.get('https://finviz.com/insidertrading.ashx?tc=7')
    transaction_table = driver.find_element_by_class_name('body-table')

    insider_trading = {}
    transactions = transaction_table.find_elements_by_tag_name("tr")
    for i in range(0, len(transactions)):

        row = transactions[i].find_elements_by_tag_name("td")
        if len(row) == 10 and i != 0:

            ticker = row[0].text
            owner = row[1].text
            number_of_shares = float(row[6].text.replace(',', ''))
            shares_total = float(row[8].text.replace(',', ''))

            if row[4].text != 'Sale' and row[4].text != 'Option Exercise':

                if ticker not in insider_trading.keys():
                    insider_trading[ticker] = {owner: {'number_of_shares': number_of_shares,
                                                       'shares_total': shares_total, 'date': row[3].text}}

                elif owner not in insider_trading[ticker].keys():
                    insider_trading[ticker][owner] = {'number_of_shares': number_of_shares,
                                                      'shares_total': shares_total, 'date': row[3].text}

                else:
                    current_number_of_shares = insider_trading[ticker][owner]['number_of_shares']
                    insider_trading[ticker][owner]['number_of_shares'] = number_of_shares + current_number_of_shares

    driver.quit()
    return insider_trading


def get_percentage_stock_traded_on(tickers_and_transactions):

    tickers = list(tickers_and_transactions.keys())
    for ticker in tickers:

        owners = tickers_and_transactions[ticker].keys()

        for owner in owners:

            entry = tickers_and_transactions[ticker][owner]
            number_of_shares = entry['number_of_shares']
            total_shares = entry['shares_total']

            percentage = 0
            if total_shares != 0:
                percentage = (float(number_of_shares) / float(total_shares)) * 100

            tickers_and_transactions[ticker][owner]['percentage'] = percentage
    return tickers_and_transactions

if __name__ == '__main__':
    driver = webdriver.Chrome(ChromeDriverManager().install())
    urls = get_trader_urls(driver)

    all_transactions = 'Top Analyst Transactions\n'
    for url in urls:
        all_transactions = all_transactions + get_trader_transactions(driver, url)

    insider_transactions = get_insider_transactions(driver)
    insider_transactions = get_percentage_stock_traded_on(insider_transactions)

    email = ''

    for ticker in insider_transactions.keys():

        owners = insider_transactions[ticker].keys()

        message = ''
        for owner in owners:
            percentage_traded = insider_transactions[ticker][owner].get('percentage')

            if percentage_traded > 5.0:
                date = insider_transactions[ticker][owner].get('date')
                message = message + f'\t insider BOUGHT {round(percentage_traded, 2)}% on {date}\n'

            if len(message) > 0:
                print(f'{ticker}\n' + message)
                email = email + f'{ticker}\n' + message


    #add in email
    send_email(email)