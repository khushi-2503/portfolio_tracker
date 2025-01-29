from flask import Flask,request,jsonify,render_template,send_file
import random
import requests
import sqlite3
import logging
import csv
from io import StringIO,BytesIO

app = Flask(__name__)

DATABASE='database.db'
API_URL="https://finnhub.io/api/v1"
API_KEY="cuagfhpr01qof06ifmq0cuagfhpr01qof06ifmqg"


logging.basicConfig(level=logging.DEBUG)

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('PRAGMA journal_mode=WAL;')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            ticker TEXT NOT NULL UNIQUE,
            quantity INTEGER NOT NULL DEFAULT 1,
            buy_price REAL NOT NULL,
            sector TEXT DEFAULT "Uncategorized"
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    return sqlite3.connect(DATABASE)



def get_stock_price(ticker):
    try:
        params = {
            'symbol': ticker,
            'token': API_KEY
        }
   
        response = requests.get(f"{API_URL}/quote", params=params)
        data = response.json()

        if 'c' in data:  
            return float(data['c'])
        elif "error" in data:
            logging.error(f"Error fetching data for ticker {ticker}: {data['error']}")
            return None
        else:
            logging.error(f"Unexpected response format for {ticker}: {data}")
            return None
    except Exception as e:
        logging.error(f"Error fetching stock price for {ticker}: {e}")
        return None



@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, ticker, quantity, buy_price, sector FROM stocks")
        rows = cursor.fetchall()
        conn.close()

        portfolio = []
        for row in rows:
            stock_id, name, ticker, quantity, buy_price, sector = row
            current_price = get_stock_price(ticker)
            portfolio.append({
                'id': stock_id,
                'name': name,
                'ticker': ticker,
                'quantity': quantity,
                'buy_price': buy_price,
                'current_price': current_price,
                'sector': sector
            })

        return jsonify(portfolio)
    except Exception as e:
        logging.error(f"Error fetching portfolio: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate_random_stocks', methods=['POST'])
def generate_random_stocks():
    try:
        sectors = ['Technology', 'Healthcare', 'Finance', 'Energy', 'Retail']
        tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'JNJ', 'JPM', 'XOM', 'WMT', 'NVDA']
        names=['Apple Inc.','Microsoft Corporation','Alphabet Inc. (Google)','Amazon','Tesla','Johnson & Johnson',' JPMorgan Chase & Co.','Exxon Mobil Corporation','Walmart Inc.','NVIDIA']

        random_stocks = []
        for ticker in random.sample(tickers, 5):
            current_price = get_stock_price(ticker)
            if current_price is None:
                continue
            random_stocks.append({
                "name": names[tickers.index(ticker)],
                "ticker": ticker,
                "quantity": random.randint(1, 100),
                "buy_price": round(random.uniform(current_price * 0.8, current_price * 1.2), 2),
                "sector": random.choice(sectors)
            })

        conn = get_db_connection()
        cursor = conn.cursor()
        for stock in random_stocks:
            cursor.execute('''
                INSERT INTO stocks (name, ticker, quantity, buy_price, sector)
                VALUES (?, ?, ?, ?, ?)
            ''', (stock["name"], stock["ticker"], stock["quantity"], stock["buy_price"], stock["sector"]))
        conn.commit()
        conn.close()

        return jsonify({'message': 'Random stocks generated successfully!'})
    except Exception as e:
        logging.error(f"Error generating random stocks: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/portfolio_insights', methods=['GET'])
def portfolio_insights():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, ticker, quantity, buy_price FROM stocks")
        rows = cursor.fetchall()

        total_value = 0
        total_profit_loss = 0
        best_stock = {'name': '', 'ticker': '', 'profit_percentage': -float('inf')}
        worst_stock = {'name': '', 'ticker': '', 'loss_percentage': float('inf')}
        other_stocks = []

        for row in rows:
            stock_id, name, ticker, quantity, buy_price = row
            current_price = get_stock_price(ticker)
            if current_price is None:
                continue

            stock_value = current_price * quantity
            profit_loss = (current_price - buy_price) * quantity
            profit_percentage = (profit_loss / (buy_price * quantity)) * 100
            loss_percentage = -profit_percentage  

            total_value += stock_value
            total_profit_loss += profit_loss
            other_stocks.append({
                'name': name,
                'ticker': ticker,
                'profit_percentage': profit_percentage,
                'loss_percentage': loss_percentage
            })

        for stock in other_stocks:
            if stock['profit_percentage'] > best_stock['profit_percentage']:
                best_stock = stock

            if stock['loss_percentage'] < worst_stock['loss_percentage']:
                worst_stock = stock

        if best_stock['name'] == worst_stock['name']:
           
            other_stocks.sort(key=lambda x: x['profit_percentage'], reverse=True)
            best_stock = other_stocks[0]
            worst_stock = other_stocks[-1]
        best_stock['profit_or_loss'] = 'Profit' if best_stock['profit_percentage'] > 0 else 'Loss'
        worst_stock['profit_or_loss'] = 'Loss' if worst_stock['loss_percentage'] > 0 else 'Profit'

        conn.close()
        return jsonify({
            'best_stock': best_stock,
            'worst_stock': worst_stock,
            'total_value': total_value,
            'total_profit_loss': total_profit_loss
        })

    except Exception as e:
        logging.error(f"Error fetching portfolio insights: {e}")
        return jsonify({'error': str(e)}), 500


    

from io import BytesIO  


@app.route('/api/export_portfolio', methods=['GET'])
def export_portfolio():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, ticker, quantity, buy_price, last_price, sector FROM stocks")
        rows = cursor.fetchall()
        conn.close()
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Name", "Ticker", "Quantity", "Buy Price", "Last Price", "Sector"])
        writer.writerows(rows)
        output.seek(0)
        csv_data = output.getvalue().encode('utf-8')
        csv_file = BytesIO(csv_data)

        return send_file(csv_file, mimetype='text/csv', as_attachment=True, download_name='portfolio.csv')
    except Exception as e:
        logging.error(f"Error exporting portfolio: {e}")
        return jsonify({'error': str(e)}), 500
    


@app.route('/api/filter_stocks', methods=['GET'])
def filter_stocks():
    try:
        sector = request.args.get('sector')
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT id, name, ticker, quantity, buy_price, last_price, sector FROM stocks WHERE sector = ?"
        cursor.execute(query, (sector,))
        rows = cursor.fetchall()
        conn.close()
        return jsonify({'stocks': rows})
    except Exception as e:
        logging.error(f"Error filtering stocks: {e}")
        return jsonify({'error': str(e)}), 500
    

@app.route('/api/add_stock', methods=['POST'])
def add_stock():
    try:
        data = request.get_json()
        name = data.get('name')
        ticker = data.get('ticker')
        quantity = data.get('quantity', 1)
        buy_price = data.get('buy_price')
        sector = data.get('sector', 'Uncategorized')

        if not all([name, ticker, buy_price]):
            return jsonify({'error': 'All fields (name, ticker, buy_price) are required!'}), 400

        current_price = get_stock_price(ticker)
        if current_price is None:
            return jsonify({'error': f'Could not fetch the current price for {ticker}'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO stocks (name, ticker, quantity, buy_price, sector, last_price)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, ticker.upper(), quantity, buy_price, sector, current_price))
        conn.commit()
        conn.close()

        return jsonify({'message': f'Stock {ticker} added successfully!'})
    except sqlite3.IntegrityError as e:
        logging.error(f"Database integrity error: {e}")
        return jsonify({'error': 'Stock with this ticker already exists!'}), 400
    except Exception as e:
        logging.error(f"Error adding stock: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/edit_stock/<int:stock_id>', methods=['PUT'])
def edit_stock(stock_id):
    try:
        data = request.get_json()
        name = data.get('name')
        ticker = data.get('ticker')
        quantity = data.get('quantity', 1)
        buy_price = data.get('buy_price')
        sector = data.get('sector', 'Uncategorized')

        if not all([name, ticker, buy_price]):
            return jsonify({'error': 'All fields (name, ticker, buy_price) are required!'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''UPDATE stocks SET name = ?, ticker = ?, quantity = ?, buy_price = ?, sector = ? WHERE id = ?''',
                       (name, ticker.upper(), quantity, buy_price, sector, stock_id))
        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({'error': 'Stock ID not found'}), 404

        conn.close()
        return jsonify({'message': 'Stock updated successfully!'})
    except Exception as e:
        logging.error(f"Error editing stock: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/delete_stock/<int:stock_id>', methods=['DELETE'])
def delete_stock(stock_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM stocks WHERE id = ?', (stock_id,))
        conn.commit()
        conn.close()

        return jsonify({'message': 'Stock deleted successfully!'})
    except Exception as e:
        logging.error(f"Error deleting stock: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/get_stock/<int:stock_id>', methods=['GET'])
def get_stock(stock_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, ticker, quantity, buy_price, sector FROM stocks WHERE id = ?", (stock_id,))
        stock = cursor.fetchone()
        conn.close()

        if stock is None:
            return jsonify({'error': 'Stock not found'}), 404

        stock_details = {
            'id': stock[0],
            'name': stock[1],
            'ticker': stock[2],
            'quantity': stock[3],
            'buy_price': stock[4],
            'sector': stock[5]
        }

        return jsonify(stock_details)

    except Exception as e:
        logging.error(f"Error fetching stock details: {e}")
        return jsonify({'error': str(e)}), 500



if __name__ == '__main__':
    app.run(debug=True)
