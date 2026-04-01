CREATE TABLE IF NOT EXISTS lme_users (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    line_name VARCHAR(255) NULL,
    href VARCHAR(1024) NULL,
    support VARCHAR(255) NULL,
    friend_registered_at DATETIME NULL,
    tags TEXT NULL,
    display_name VARCHAR(255) NULL,
    friend_value JSON NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_lme_users_href (href(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS lme_messages (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NOT NULL,
    sender_name VARCHAR(255) NULL,
    sender VARCHAR(16) NOT NULL,
    message LONGTEXT NOT NULL,
    time_sent DATETIME NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_lme_messages_user_id (user_id),
    KEY idx_lme_messages_time_sent (time_sent),
    CONSTRAINT fk_lme_messages_user_id
      FOREIGN KEY (user_id) REFERENCES lme_users(id)
      ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
