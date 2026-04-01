<?php
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');

require_once __DIR__ . '/config.php';

function respond(array $payload, int $status = 200): void {
    http_response_code($status);
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

try {
    $raw = file_get_contents('php://input');
    $input = json_decode($raw ?: '{}', true);
    if (!is_array($input)) {
        respond(['ok' => false, 'error' => 'invalid_json'], 400);
    }

    $action = $input['action'] ?? null;
    $payload = $input['payload'] ?? [];
    if (!is_string($action) || $action === '') {
        respond(['ok' => false, 'error' => 'missing_action'], 400);
    }

    $dsn = sprintf('mysql:host=%s;dbname=%s;charset=%s', DB_HOST, DB_NAME, DB_CHARSET);
    $pdo = new PDO($dsn, DB_USER, DB_PASS, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    ]);

    switch ($action) {
        case 'initialize_tables':
            $pdo->exec(
                "CREATE TABLE IF NOT EXISTS lme_users (
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
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            );
            $pdo->exec(
                "CREATE TABLE IF NOT EXISTS lme_messages (
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
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            );
            respond(['ok' => true]);

        case 'clear_tables':
            $pdo->beginTransaction();
            $pdo->exec('DELETE FROM lme_messages');
            $pdo->exec('DELETE FROM lme_users');
            $pdo->commit();
            respond(['ok' => true]);

        case 'upsert_user':
            $href = $payload['href'] ?? null;
            if (!is_string($href) || $href === '') {
                respond(['ok' => false, 'error' => 'href_required'], 400);
            }

            $lineName = $payload['line_name'] ?? null;
            $friendRegisteredAt = $payload['friend_registered_at'] ?? null;
            $support = $payload['support'] ?? null;
            $displayName = $payload['display_name'] ?? null;

            $findStmt = $pdo->prepare('SELECT id FROM lme_users WHERE href = :href ORDER BY id ASC LIMIT 1');
            $findStmt->execute([':href' => $href]);
            $row = $findStmt->fetch();

            if ($row) {
                $updateStmt = $pdo->prepare(
                    'UPDATE lme_users
                     SET line_name = :line_name, href = :href, friend_registered_at = :friend_registered_at,
                         support = :support, display_name = :display_name
                     WHERE id = :id'
                );
                $updateStmt->execute([
                    ':line_name' => $lineName,
                    ':href' => $href,
                    ':friend_registered_at' => $friendRegisteredAt,
                    ':support' => $support,
                    ':display_name' => $displayName,
                    ':id' => (int)$row['id'],
                ]);
                respond(['ok' => true, 'data' => ['id' => (int)$row['id']]]);
            }

            $insertStmt = $pdo->prepare(
                'INSERT INTO lme_users (line_name, href, friend_registered_at, support, display_name)
                 VALUES (:line_name, :href, :friend_registered_at, :support, :display_name)'
            );
            $insertStmt->execute([
                ':line_name' => $lineName,
                ':href' => $href,
                ':friend_registered_at' => $friendRegisteredAt,
                ':support' => $support,
                ':display_name' => $displayName,
            ]);
            respond(['ok' => true, 'data' => ['id' => (int)$pdo->lastInsertId()]]);

        case 'list_users':
            $stmt = $pdo->query('SELECT id, href FROM lme_users ORDER BY id ASC');
            respond(['ok' => true, 'data' => $stmt->fetchAll()]);

        case 'insert_message':
            $stmt = $pdo->prepare(
                'INSERT INTO lme_messages (user_id, sender_name, sender, message, time_sent)
                 VALUES (:user_id, :sender_name, :sender, :message, :time_sent)'
            );
            $stmt->execute([
                ':user_id' => (int)($payload['user_id'] ?? 0),
                ':sender_name' => $payload['sender_name'] ?? null,
                ':sender' => (string)($payload['sender'] ?? ''),
                ':message' => (string)($payload['message'] ?? ''),
                ':time_sent' => (string)($payload['time_sent'] ?? ''),
            ]);
            respond(['ok' => true, 'data' => ['id' => (int)$pdo->lastInsertId()]]);

        default:
            respond(['ok' => false, 'error' => 'unknown_action'], 400);
    }
} catch (Throwable $e) {
    respond(['ok' => false, 'error' => $e->getMessage()], 500);
}
