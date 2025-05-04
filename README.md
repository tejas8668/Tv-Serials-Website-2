# Flask MongoDB App

This project is a web application built using Flask that fetches data from a MongoDB database and displays it in a paginated format. The application allows users to navigate through the files with "Next Page" and "Previous Page" buttons.

## Project Structure

```
flask-mongodb-app
├── src
│   ├── static
│   │   ├── css
│   │   │   └── styles.css
│   │   └── js
│   │       └── script.js
│   ├── templates
│   │   ├── base.html
│   │   └── index.html
│   ├── app.py
│   ├── config.py
│   └── database.py
├── requirements.txt
├── .env
└── README.md
```

## Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd flask-mongodb-app
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install the required dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   Create a `.env` file in the root directory and add your MongoDB URI:
   ```
   MONGO_URI="your_mongodb_uri_here"
   ```

5. **Run the application:**
   ```bash
   python src/app.py
   ```

6. **Access the application:**
   Open your web browser and go to `http://127.0.0.1:5000/`.

## Usage

- The main page will display files fetched from the MongoDB database.
- Use the pagination controls to navigate through the files.
- Each page displays 40 files at a time.

## License

This project is licensed under the MIT License.