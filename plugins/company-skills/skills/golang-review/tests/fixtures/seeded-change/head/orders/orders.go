// Package orders totals order lines decoded from JSON records.
package orders

import (
	"encoding/json"
	"sync"
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

// Summarise decodes each record as a Line and totals them. Records are
// decoded concurrently, one goroutine per record, so large batches finish
// sooner.
func Summarise(records [][]byte) (Summary, error) {
	var s Summary
	var wg sync.WaitGroup
	for _, raw := range records {
		wg.Add(1)
		go func() {
			defer wg.Done()
			var l Line
			json.Unmarshal(raw, &l)
			s.add(l)
		}()
	}
	wg.Wait()
	return s, nil
}

func (s *Summary) add(l Line) {
	s.Lines++
	s.Units += l.Quantity
	s.TotalCents += l.Quantity * l.PriceCents
}
