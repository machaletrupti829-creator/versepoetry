create database versepoetry_db;
use versepoetry_db;
-- 1. Users Table
CREATE TABLE users ( user_id INT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(100) NOT NULL, email VARCHAR(150) UNIQUE NOT NULL, registration_date DATETIME, contact_number VARCHAR(15) UNIQUE, password_hash VARCHAR(255) );
-- 2. Poems Table 
CREATE TABLE poems ( poem_id INT PRIMARY KEY AUTO_INCREMENT, user_id INT NOT NULL, title VARCHAR(200) NOT NULL, content TEXT NOT NULL, file_path VARCHAR(255), status VARCHAR(20) DEFAULT 'Pending', created_at DATETIME, FOREIGN KEY (user_id) REFERENCES users(user_id) );
-- 3. Admin Table 
CREATE TABLE admins ( admin_id INT PRIMARY KEY AUTO_INCREMENT, admin_name VARCHAR(100), username VARCHAR(100) UNIQUE NOT NULL, password_hash VARCHAR(255) NOT NULL, created_at DATETIME );
-- 4. Contact Messages Table
 CREATE TABLE contact_messages ( message_id INT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(100) NOT NULL, email VARCHAR(150) NOT NULL, message TEXT NOT NULL, created_at DATETIME );
-- 5. QR Login Requests Table 
CREATE TABLE qr_login_requests ( request_id INT PRIMARY KEY AUTO_INCREMENT, token_hash VARCHAR(255) UNIQUE NOT NULL, status VARCHAR(20) DEFAULT 'pending', user_id INT, created_at DATETIME, expires_at DATETIME, FOREIGN KEY (user_id) REFERENCES users(user_id) );
-- 6. Remembered Devices Table
 CREATE TABLE remembered_devices ( device_id INT PRIMARY KEY AUTO_INCREMENT, user_id INT NOT NULL, token_hash VARCHAR(255) UNIQUE NOT NULL, created_at DATETIME, FOREIGN KEY (user_id) REFERENCES users(user_id) );
 
 -- 1. Display all users
SELECT * FROM users;

-- 2. Display all poems
SELECT * FROM poems;

-- 3. Display pending poems for admin
SELECT * FROM poems
WHERE status = 'Pending';

-- 4. Approve a poem
UPDATE poems
SET status = 'Approved'
WHERE poem_id = 1;

-- 5. Reject a poem
UPDATE poems
SET status = 'Rejected'
WHERE poem_id = 1;

-- 6. Display approved poems
SELECT * FROM poems
WHERE status = 'Approved';

-- 7. Display rejected poems
SELECT * FROM poems
WHERE status = 'Rejected';

-- 8. Count total users
SELECT COUNT(*) AS total_users
FROM users;

-- 9. Count total poems
SELECT COUNT(*) AS total_poems
FROM poems;

-- 10. Count poems by status
SELECT status, COUNT(*) AS total
FROM poems
GROUP BY status;

-- 11. Display poems in latest order
SELECT * FROM poems
ORDER BY created_at DESC;

-- 12. Display user names and their poems
SELECT users.name, poems.title, poems.status
FROM users
INNER JOIN poems
ON users.user_id = poems.user_id;

-- 13. Display all users, including users
-- who have not submitted poems
SELECT users.name, poems.title
FROM users
LEFT JOIN poems
ON users.user_id = poems.user_id;

-- 14. Find users who have submitted poems
SELECT * FROM users
WHERE user_id IN (
    SELECT user_id FROM poems
);

-- 15. Count poems submitted by each user
SELECT user_id, COUNT(*) AS total_poems
FROM poems
GROUP BY user_id;

-- 16. Find users with more than one poem
SELECT user_id, COUNT(*) AS total_poems
FROM poems
GROUP BY user_id
HAVING COUNT(*) > 1;

-- 17. Search poems by title
SELECT * FROM poems
WHERE title LIKE '%search_word%';

-- 18. Display all contact messages
SELECT * FROM contact_messages;

-- 19. Display QR login requests
SELECT * FROM qr_login_requests;

-- 20. Display remembered devices
SELECT * FROM remembered_devices;

SELECT users.name, COUNT(poems.poem_id) AS total_poems
FROM users
LEFT JOIN poems
ON users.user_id = poems.user_id
GROUP BY users.user_id, users.name;

SELECT *
FROM users
WHERE user_id NOT IN (
    SELECT user_id
    FROM poems
);
SELECT *
FROM users
ORDER BY registration_date DESC;

SELECT DISTINCT status
FROM poems;

UPDATE poems
SET status = 'Approved'
WHERE poem_id = 2;

SELECT *
FROM poems
WHERE poem_id = 2;

SELECT user_id, COUNT(*) AS total_poems
FROM poems
GROUP BY user_id
ORDER BY total_poems DESC
LIMIT 1;

CREATE VIEW approved_poems AS
SELECT poem_id, user_id, title, content, created_at
FROM poems
WHERE status = 'Approved';

SELECT * FROM approved_poems;

CREATE INDEX idx_poem_status
ON poems(status);

SHOW INDEX FROM poems;

DESCRIBE users;
DELETE FROM contact_messages
WHERE message_id = 1;
SELECT
    MIN(poem_id) AS first_poem_id,
    MAX(poem_id) AS last_poem_id
FROM poems;

START TRANSACTION;

UPDATE poems
SET status = 'Approved'
WHERE poem_id = 1;

SELECT *
FROM poems
WHERE poem_id = 1;

ROLLBACK;

CREATE TABLE poem_status_history (
    history_id INT PRIMARY KEY AUTO_INCREMENT,
    poem_id INT,
    old_status VARCHAR(20),
    new_status VARCHAR(20),
    changed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

DELIMITER //

CREATE TRIGGER poem_status_update
AFTER UPDATE ON poems
FOR EACH ROW
BEGIN
    IF OLD.status <> NEW.status THEN
        INSERT INTO poem_status_history
            (poem_id, old_status, new_status)
        VALUES
            (OLD.poem_id, OLD.status, NEW.status);
    END IF;
END //

DELIMITER ;


DELIMITER //

CREATE PROCEDURE GetPendingPoems()
BEGIN
    SELECT *
    FROM poems
    WHERE status = 'Pending';
END //

DELIMITER ;

CALL GetPendingPoems();

SHOW TRIGGERS;
SELECT * FROM poem_status_history;

SELECT status, COUNT(*) AS total_poems
FROM poems
GROUP BY status;

SELECT user_id, name, email
FROM users
WHERE user_id IN (
    SELECT DISTINCT user_id
    FROM poems
);

SELECT *
FROM poem_status_history
ORDER BY changed_at DESC;

SELECT
    u.user_id,
    u.name,
    COUNT(p.poem_id) AS total_poems
FROM users AS u
LEFT JOIN poems AS p
    ON u.user_id = p.user_id
GROUP BY u.user_id, u.name
ORDER BY total_poems DESC;


USE versepoetry_db;

DELIMITER //

CREATE PROCEDURE GetUserPoems(IN p_user_id INT)
BEGIN
    SELECT poem_id, title, status, created_at
    FROM poems
    WHERE user_id = p_user_id;
END //

DELIMITER ;


CALL GetUserPoems(1);


DELIMITER //

CREATE PROCEDURE GetPoemCount(
    IN p_user_id INT,
    OUT p_total INT
)
BEGIN
    SELECT COUNT(*)
    INTO p_total
    FROM poems
    WHERE user_id = p_user_id;
END //

DELIMITER ;


CALL GetPoemCount(1, @total);

SELECT @total AS total_poems;

DELIMITER //

CREATE PROCEDURE IncreaseCount(INOUT p_count INT)
BEGIN
    SET p_count = p_count + 1;
END //

DELIMITER ;

SET @count = 5;

CALL IncreaseCount(@count);

SELECT @count AS updated_count;

SELECT user_id, name
FROM users
WHERE user_id IN (
    SELECT user_id
    FROM poems
    GROUP BY user_id
    HAVING COUNT(*) > (
        SELECT AVG(poem_count)
        FROM (
            SELECT COUNT(*) AS poem_count
            FROM poems
            GROUP BY user_id
        ) AS poem_totals
    )
);

SELECT poem_id, title, status, created_at
FROM poems
WHERE created_at = (
    SELECT MAX(created_at)
    FROM poems
);

SELECT user_id, name, email
FROM users
WHERE user_id NOT IN (
    SELECT user_id
    FROM poems
);

SELECT poem_id, title, status, created_at
FROM poems
WHERE DATE(created_at) = CURDATE();

SELECT NOW() AS current_datetime;

SELECT CURDATE() AS today_date;

SELECT
    poem_id,
    title,
    YEAR(created_at) AS submission_year
FROM poems;

SELECT
    poem_id,
    title,
    MONTH(created_at) AS submission_month
FROM poems;

SELECT poem_id, title, created_at
FROM poems
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY);

SELECT poem_id, title, created_at
FROM poems
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY);

SELECT DATE_ADD(CURDATE(), INTERVAL 7 DAY)
AS date_after_7_days;

SELECT
    poem_id,
    title,
    DATEDIFF(CURDATE(), DATE(created_at))
    AS days_since_submission
FROM poems;

SELECT UPPER(name) AS uppercase_name
FROM users;
SELECT LOWER(name) AS lowercase_name
FROM users;
SELECT
    name,
    LENGTH(name) AS name_length
FROM users;
SELECT
    title,
    SUBSTRING(title, 1, 10) AS short_title
FROM poems;
SELECT CONCAT(name, ' - ', email) AS user_details
FROM users;
SELECT TRIM(title) AS cleaned_title
FROM poems;

DELIMITER //

CREATE PROCEDURE CountPendingPoems()
BEGIN
    DECLARE done INT DEFAULT 0;
    DECLARE current_poem_id INT;
    DECLARE total_pending INT DEFAULT 0;

    DECLARE poem_cursor CURSOR FOR
        SELECT poem_id
        FROM poems
        WHERE status = 'Pending';

    DECLARE CONTINUE HANDLER FOR NOT FOUND
        SET done = 1;

    OPEN poem_cursor;

    read_loop: LOOP
        FETCH poem_cursor INTO current_poem_id;

        IF done = 1 THEN
            LEAVE read_loop;
        END IF;

        SET total_pending = total_pending + 1;
    END LOOP;

    CLOSE poem_cursor;

    SELECT total_pending AS pending_poems_count;
END //

DELIMITER ;


CALL CountPendingPoems();


USE versepoetry_db;

DESCRIBE users;
DESCRIBE poems;
DESCRIBE admins;
DESCRIBE contact_messages;
DESCRIBE qr_login_requests;
DESCRIBE remembered_devices;


USE versepoetry_db;

SELECT * FROM users;

SELECT * FROM poems;

select * from users  where user_id = 1;

