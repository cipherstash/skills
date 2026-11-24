// Package orders totals order lines decoded from JSON records.
package orders

import (
	"encoding/json"
	"fmt"
)

// Line is one order line.
type Line struct {
	SKU        string `json:"sku"`
	Quantity   int    `json:"quantity"`
	PriceCents int    `json:"price_cents"`
}

// Summary totals a batch of order lines.
type Summary struct {
	Lines      int
	Units      int
	TotalCents int
}

// Summarise decodes each record as a Line and totals them. It returns an
// error naming the first record that does not decode.
func Summarise(records [][]byte) (Summary, error) {
	var s Summary
	for i, raw := range records {
		var l Line
		if err := json.Unmarshal(raw, &l); err != nil {
			return Summary{}, fmt.Errorf("decode record %d: %w", i, err)
		}
		s.add(l)
	}
	return s, nil
}

func (s *Summary) add(l Line) {
	s.Lines++
	s.Units += l.Quantity
	s.TotalCents += l.Quantity * l.PriceCents
}

// Empty reports whether s has no lines.
func (s Summary) Empty() bool {
	return s.Lines == 0
}
