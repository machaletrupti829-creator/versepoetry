import mysql.connector

try:
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Trupti@11",
        database="versepoetry_db"
    )

    if connection.is_connected():
        print("MySQL connection successful!")

    connection.close()

except mysql.connector.Error as error:
    print("MySQL connection failed:", error)