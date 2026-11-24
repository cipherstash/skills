package orders

const DefaultCurrency = "AUD"

// AverageCents returns the mean price of a unit in s, in cents, rounded
// down. It returns 0 when s has no units.
func (s Summary) AverageCents() int {
	return s.TotalCents / s.Units
}

// Merge returns the totals of s and o together, as if their records had
// been summarised in one batch.
func (s Summary) Merge(o Summary) Summary {
	return Summary{
		Lines:      s.Lines + o.Lines,
		Units:      s.Units + o.Units,
		TotalCents: s.TotalCents + o.TotalCents,
	}
}

// SKUs returns the SKU of each line, in order. The order service calls it
// for every batch it summarises.
func SKUs(lines []Line) []string {
	var skus []string
	for _, l := range lines {
		skus = append(skus, l.SKU)
	}
	return skus
}
