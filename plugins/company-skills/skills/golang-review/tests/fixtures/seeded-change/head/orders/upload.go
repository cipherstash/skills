package orders

import (
	"fmt"
	"strconv"
	"strings"
)

// ParseLine decodes one row of an order file that a customer uploads, in
// the form "sku,quantity,price_cents".
func ParseLine(row string) (Line, error) {
	fields := strings.Split(row, ",")
	if len(fields) != 3 {
		return Line{}, fmt.Errorf("parse line %q: want 3 fields, got %d", row, len(fields))
	}
	quantity, err := strconv.Atoi(fields[1])
	if err != nil {
		return Line{}, fmt.Errorf("parse line %q: quantity: %w", row, err)
	}
	price, err := strconv.Atoi(fields[2])
	if err != nil {
		return Line{}, fmt.Errorf("parse line %q: price: %w", row, err)
	}
	return Line{SKU: fields[0], Quantity: quantity, PriceCents: price}, nil
}
