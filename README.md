# Simple Stock Simulator

A clean and interactive stock trading simulator that lets users practice buying, selling, tracking history, and monitoring performance — all without real money.

## 🚀 Features

* **Buy & Sell Stocks** with instant portfolio updates
* **Auto-updating Ticker** display
* **Portfolio Summary** with invested capital, profit/loss, and performance
* **Trade History** with CSV export
* **Reset Portfolio** option
* **Clean Frontend UI** using HTML/CSS/JS
* **Backend API** built with Python (Flask)

## 📁 Project Structure

```
simple_stock_simulator.project/
│
├── data/
│   └── portfolio.json
├── static/
│   ├── style.css
│   ├── script.js
│   └── index.html
├── trading.py
├── main.py
├── app.py
├── requirements.txt
└── README.md
```

## ⚙️ Setup & Installation

### 1. Clone the repository

```
git clone https://github.com/567darshan/simple-_stock_simulator.project.git
cd simple-_stock_simulator.project
```

### 3. Install dependencies

```
pip install -r requirements.txt
```

### 4. Run the server

```
python app.py
```

Open in browser:

```
http://127.0.0.1:5001
```

## 📡 API Endpoints

| Endpoint           | Method | Description           |
| ------------------ | ------ | --------------------- |
| `/api/buy`         | POST   | Buy a stock           |
| `/api/sell`        | POST   | Sell a stock          |
| `/api/history`     | GET    | Get trade history     |
| `/api/history_csv` | GET    | Export history CSV    |
| `/api/reset`       | POST   | Reset portfolio       |
| `/api/stats`       | GET    | Get performance stats |
| `/api/performance` | GET    | Calculate gain/loss   |

## 🧠 How It Works

* Each stock price is fetched or simulated
* User actions update `portfolio.json`
* Frontend polls backend for stats (AJAX)
* History logs every trade with timestamp

## 👨‍💻 Contributors

* **Hardik K M** – Backend Developer
* **Darshan A** – Frontend/UI Contributor

"Designed by Hardik K M & Darshan A"

## ⭐ Future Enhancements

* Add login/authentication
* Add charts (profit timeline, value trends)
* Add multi-user support
* Deploy on Render/Heroku

## 📜 License

This project is open-source under the MIT License.
