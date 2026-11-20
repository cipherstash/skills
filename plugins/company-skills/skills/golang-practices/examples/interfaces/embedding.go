package interfaces

import "fmt"

// Logger records messages.
type Logger interface {
	Log(msg string)
}

// discard is a Logger that drops every message.
type discard struct{}

func (discard) Log(string) {}

// Importer embeds a Logger, so its Log method is promoted: imp.Log(...)
// calls the embedded logger.
type Importer struct {
	Logger
}

// NewImporter returns an Importer that logs to logger, or discards messages
// when logger is nil, so the embedded interface is never nil.
func NewImporter(logger Logger) *Importer {
	if logger == nil {
		logger = discard{}
	}
	return &Importer{Logger: logger}
}

// Import records that it imported n rows.
func (imp *Importer) Import(n int) {
	imp.Log(fmt.Sprintf("imported %d rows", n))
}
