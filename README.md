# LUAX Health Plus

LUAX Health Plus is a web application for a clinic that allows patients to book appointments, check their appointment status, and manage their health records. The application also provides an admin interface for clinic staff to manage appointments and patients.

## Features

*   **Patient Portal:**
    *   Book new appointments.
    *   Check the status of existing appointments.
    *   Update appointment details.
    *   Cancel pending appointments.
    *   User registration and login.
*   **Admin Panel:**
    *   View all appointments.
    *   Mark appointments as read/unread.
    *   Manage patient records.
*   **Email Notifications:**
    *   Admins receive an email for new appointment bookings.
    *   Patients and admins receive an email when an appointment is cancelled.

## Project Structure

```
.
├── admin/                  # Admin blueprint (routes and templates)
├── data/                   # SQLite database file
├── patients/               # Patients blueprint (routes and templates)
├── static/                 # Static assets (CSS, JS, images)
├── templates/              # HTML templates
├── .env                    # Environment variables
├── app.log                 # Application log file
├── app.py                  # Main Flask application file
├── database.py             # Database initialization and connection
├── requirements.txt        # Python dependencies
└── utils.py                # Utility functions
```

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

*   Python 3.6+
*   pip

### Installing

1.  Clone the repository:
    ```bash
    git clone https://github.com/your-username/luax-health-plus.git
    ```
2.  Install the dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Create a `.env` file in the root directory and add the following environment variables:
    ```
    CLINIC_EMAIL=your-email@example.com
    CLINIC_EMAIL_PASSWORD=your-email-password
    ADMIN_PASSWORD=your-admin-password
    SECRET_KEY=your-secret-key
    ```
4.  Run the application:
    ```bash
    python app.py
    ```

The application will be running at `http://localhost:5000`.
