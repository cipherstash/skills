package orders

import (
	"slices"
	"testing"
)

func TestAverageCents(t *testing.T) {
	s := Summary{Lines: 2, Units: 3, TotalCents: 1299}
	if got := s.AverageCents(); got != 433 {
		t.Errorf("AverageCents() = %d, want 433", got)
	}
}

func TestSKUs(t *testing.T) {
	lines := []Line{{SKU: "A1"}, {SKU: "B2"}}
	if got, want := SKUs(lines), []string{"A1", "B2"}; !slices.Equal(got, want) {
		t.Errorf("SKUs = %q, want %q", got, want)
	}
}

func TestLinesQuery(t *testing.T) {
	want := "SELECT sku, quantity, price_cents FROM order_lines WHERE sku = 'A1'"
	if got := LinesQuery("A1"); got != want {
		t.Errorf("LinesQuery(%q) = %q, want %q", "A1", got, want)
	}
}

func TestUnitsPerLine(t *testing.T) {
	tests := []struct {
		name string
		s    Summary
		want float64
	}{
		{"empty", Summary{}, 0},
		{"two lines", Summary{Lines: 2, Units: 3}, 1.5},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := tt.s.UnitsPerLine(); got != tt.want {
				t.Errorf("UnitsPerLine() = %v, want %v", got, tt.want)
			}
		})
	}
}
