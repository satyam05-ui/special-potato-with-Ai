🛠️ Tech StackFrontend: 
HTML5, CSS3 (Glassmorphism UI), Vanilla JavaScript, Chart.js, and Phosphor Icons. 
Backend: Python, Flask, Flask-CORS, PyJWT, and Werkzeug.  
Database: SQLite3 (carbonwise.db).  
📂 Database SchemaThe SQLite database utilizes the following core tables to manage application 
state:  users: Stores user credentials, accumulated index points, and account creation timestamps.
calculations: Logs telemetry data across transport, energy, and diet matrices.
user_challenges: Tracks completed eco-challenges by users.
actions: Records point-awarding actions and allows for action-reversal (undo) functionality.
⚙️ Installation & SetupPrerequisites
Python 3.x installed on your local machine.
1. Download the ProjectEnsure you have the core files (app.py, index.html, and carbonwise.db) in your working directory.
2. Install DependenciesOpen your terminal and install the required Python packages for the backend:
   Bashpip install flask flask-cors PyJWT Werkzeug
3. Run the Backend ServerStart the Flask API server.
    The server will initialize the database (if it doesn't already exist) and run locally:
   Bash python app.py
The backend API will run on http://localhost:8000.
4. Launch the FrontendSimply open the index.html file in your preferred web browser, or serve it using a lightweight local development server (like VS Code's Live Server).
5. 📡 API Endpoints ReferenceThe backend exposes several RESTful APIs:

POST /calculations: Submit footprint metrics and receive a calculated emission matrix.
 GET /calculations/latest: Fetch the most recent calculation data.GET /challenges: Retrieve available eco-challenges.
 POST /challenges/<code_id>/complete: Execute a challenge protocol and earn points.
 POST /actions/undo: Revert the last recorded action and deduct points accordingly.
