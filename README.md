# VersePoetry ✍️

### A Poetry Submission and Management Platform

VersePoetry is a web-based application developed to provide a platform where users can submit their poems and track their submission status. The application includes user authentication, poem management, and an admin panel for reviewing submitted poems.

## 🚀 Features

* **User Authentication:** Login using OTP verification.
* **QR Code Login:** Provides a QR-based login option.
* **Poem Submission:** Users can submit poems through the website.
* **Submission Tracking:** Users can check their poem submission status.
* **User Profile:** Displays user-related information.
* **Admin Dashboard:** Admin can review submitted poems and approve or reject them.
* **Contact Form:** Users can send messages through the website.
* **Database Integration:** Stores application data in MySQL.

## 🛠️ Technologies Used

* Python
* Flask
* MySQL
* HTML5
* CSS3
* JavaScript
* MySQL Connector for Python

## 📂 Project Structure

```text
VersePoetry/
├── app.py
├── database.sql
├── test_mysql.py
├── templates/
├── statics/
├── uploads/
└── README.md
```

## ⚙️ Installation and Setup

### 1. Clone the Repository

```bash
git clone YOUR_REPOSITORY_URL
cd versepoetry
```

Replace `YOUR_REPOSITORY_URL` with your GitHub repository URL.

### 2. Install Dependencies

```bash
pip install flask mysql-connector-python
```

Install any additional packages required by the application.

### 3. Configure MySQL

* Start your MySQL Server.
* Create the `versepoetry_db` database.
* Create the required tables using your SQL script.
* Configure your database connection credentials using environment variables.

For PowerShell:

```powershell
$env:MYSQL_HOST="localhost"
$env:MYSQL_USER="root"
$env:MYSQL_PASSWORD="YOUR_MYSQL_PASSWORD"
$env:MYSQL_DATABASE="versepoetry_db"
```

Replace `YOUR_MYSQL_PASSWORD` with your actual MySQL password.

### 4. Run the Application

```bash
python app.py
```

Open the local URL displayed in the terminal.

## 🗄️ Database Tables

The database includes tables for:

* Users
* Poems
* Admins
* Contact Messages
* QR Login Requests
* Remembered Devices
* Approved Poems
* Poem Status History

## 🎯 Project Objective

The objective of VersePoetry is to provide a convenient platform for poem submission and review while using database management to store and manage user information, poem submissions, and approval statuses.

## 👩‍💻 Developed By

**Trupti Machale**

Computer Engineering Student

## 📌 Note

This project was developed as an academic project to demonstrate web application development, database integration, and CRUD operations using Flask and MySQL.
