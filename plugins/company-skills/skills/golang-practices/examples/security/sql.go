package security

import (
	"context"
	"database/sql"
	"fmt"
)

// Execer is the part of *sql.DB and *sql.Tx that RenameUser needs.
type Execer interface {
	ExecContext(ctx context.Context, query string, args ...any) (sql.Result, error)
}

// RenameUser sets the name of user id. The values travel as arguments, never
// as part of the SQL text, so a name such as "x'; DROP TABLE users; --" is
// stored as text and not run. Placeholders are driver-specific: $1 for
// PostgreSQL, ? for MySQL and SQLite.
func RenameUser(ctx context.Context, db Execer, id int64, name string) error {
	if _, err := db.ExecContext(ctx, "UPDATE users SET name = $1 WHERE id = $2", name, id); err != nil {
		return fmt.Errorf("rename user %d: %w", id, err)
	}
	return nil
}

// sortColumns maps the sort keys a caller may ask for to column names.
var sortColumns = map[string]string{
	"name":    "name",
	"created": "created_at",
}

// ListUsersQuery builds a query sorted by a caller-chosen column. Column
// names cannot be placeholders, so the key is checked against an allow-list
// and only a fixed string from the list reaches the SQL.
func ListUsersQuery(sortKey string) (string, error) {
	col, ok := sortColumns[sortKey]
	if !ok {
		return "", fmt.Errorf("list users: unknown sort key %q", sortKey)
	}
	return "SELECT id, name FROM users ORDER BY " + col, nil
}

// RenameUserFormatted shows the mistake RenameUser avoids: it formats the
// name into the SQL text, so a name containing a quote ends the string and
// the rest runs as SQL. Never build queries like this.
func RenameUserFormatted(ctx context.Context, db Execer, id int64, name string) error {
	query := fmt.Sprintf("UPDATE users SET name = '%s' WHERE id = %d", name, id) // wrong: injectable
	if _, err := db.ExecContext(ctx, query); err != nil {
		return fmt.Errorf("rename user %d: %w", id, err)
	}
	return nil
}
